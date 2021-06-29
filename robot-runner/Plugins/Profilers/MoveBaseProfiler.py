import os
import pandas as pd
from datetime import datetime
from paramiko import SSHClient, AutoAddPolicy
from Plugins.Profilers.LogFileProfiler import LogFileProfiler
from ProgressManager.Output.OutputProcedure import OutputProcedure


class MoveBaseProfiler(LogFileProfiler):

    def __init__(self, ip_addr, username, hostname) -> None:
        super().__init__(ip_addr, username, hostname)

    def process_log_files(self, output_folder, move_base_on_pc=True):
        ssh_client = None
        sftp_client = None
        move_base_log_file = None
        navigation_results_log_file = None

        # SSH to the remote machine
        try:
            ssh_client = SSHClient()
            ssh_client.load_host_keys(f"/home/{os.environ['USERNAME']}/.ssh/known_hosts")
            ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            ssh_client.connect(self.ip_addr, username=self.username)
            sftp_client = ssh_client.open_sftp()
            
            # If move_base node is executed on this PC, fetch the log file locally
            if move_base_on_pc:
                move_base_log_file = self.open_local_log_file("move_base")
            # Otherwise fetch the file over SFTP 
            else:
                move_base_log_file = self.open_remote_log_file(ssh_client, sftp_client, "move_base")

            # Process log file
            move_base_df = self.process_move_base_log_file(move_base_log_file)

            # Fetch remotely and process obj_recognition_results log file
            navigation_results_log_file = self.open_remote_log_file(ssh_client, sftp_client, "sherlock_controller")
            navigation_results_df = self.process_navigation_results(navigation_results_log_file)

            # Calculate the delay of receiving the detection result at the side of obj_recognition_results node in ms
            results_df = self.combine_data_frames(move_base_df, navigation_results_df)

            results_df.to_csv(os.path.join(output_folder, "move_base_results.csv"), index=False, header=True)
            OutputProcedure.console_log_OK("MoveBase profiler done")

        except BaseException as e:
            OutputProcedure.console_log_FAIL("FindObject2d profiler failed!")
            print(e)
            
        finally:
            # Close all resources that are successfully open
            if navigation_results_log_file:
                navigation_results_log_file.close()

            if move_base_log_file:
                move_base_log_file.close()

            if sftp_client:
                sftp_client.close()

            if ssh_client:
                ssh_client.close()


    def process_move_base_log_file(self, log_file):
        # Data to extract from the file
        data = {
            'goal_processed_at': [], 
            'goal_reached_at': []
        }

        # Catch only the first 'Got new plan' message after new goal is sent
        firs_goal_processing = True

        for line in log_file:
            # First time new goal is processed
            if 'Got new plan' in line and firs_goal_processing:
                # Get log time
                line = line[line.index(']') + 1 :]
                time_as_string = line[line.index('[') + 1 : line.index(']')]
                log_time = datetime.fromtimestamp(float(time_as_string))

                data['goal_processed_at'].append(log_time)
                firs_goal_processing = False
            # Destination is reached
            elif 'Goal reached' in line:
                # Get log time
                line = line[line.index(']') + 1 :]
                time_as_string = line[line.index('[') + 1 : line.index(']')]
                log_time = datetime.fromtimestamp(float(time_as_string))

                data['goal_reached_at'].append(log_time)
                firs_goal_processing = True

        return pd.DataFrame(data)


    def process_navigation_results(self, log_file):
        data = {
            'goal_sent_at': [],
            'result_received_at': []
        }

        for line in log_file:

            if 'Sending goal location' in line:
                # Get log time
                line = line[line.index(']') + 1 :]
                time_as_string = line[line.index('] ') + 2 : line.index('Sending goal location')]
                log_time = datetime.strptime(time_as_string, '%Y-%m-%d %H:%M:%S,%f: ')

                data['goal_sent_at'].append(log_time)
            elif 'The robot has reached the destination' in line:
                # Get log time
                line = line[line.index(']') + 1 :]
                time_as_string = line[line.index('] ') + 2 : line.index('The robot has reached the destination')]
                log_time = datetime.strptime(time_as_string, '%Y-%m-%d %H:%M:%S,%f: ')

                data['result_received_at'].append(log_time)

        return pd.DataFrame(data)

    def combine_data_frames(self, move_base_df, navigation_results_df):
        data = {
            'goal_sent_at': [],
            'goal_sending_delay_ms': [],
            'goal_processing_s': [],
            'result_delay_ms': []
        }

        # Time when goal location is sent
        data['goal_sent_at'] = navigation_results_df['goal_sent_at']

        # Delay to start navigating to the goal location
        data['goal_sending_delay_ms'] = move_base_df['goal_processed_at'] - navigation_results_df['goal_sent_at']
        data['goal_sending_delay_ms'] = data['goal_sending_delay_ms'].apply(lambda x: x.total_seconds() * 1000)

        # Navigation duration
        data['goal_processing_s'] = move_base_df['goal_reached_at'] - move_base_df['goal_processed_at']
        data['goal_processing_s'] = data['goal_processing_s'].apply(lambda x: x.total_seconds())

        # Receiving destination reached result delay
        data['result_delay_ms'] = navigation_results_df['result_received_at'] - move_base_df['goal_reached_at']
        data['result_delay_ms'] = data['result_delay_ms'].apply(lambda x: x.total_seconds() * 1000)

        return pd.DataFrame(data)


    def get_average_results(self, input_folder):
        input_file = os.path.join(input_folder, "move_base_results.csv")
        results_df = pd.read_csv(input_file)
        return results_df['goal_sending_delay_ms'].mean(), results_df['goal_processing_s'].mean(), results_df['result_delay_ms'].mean()

