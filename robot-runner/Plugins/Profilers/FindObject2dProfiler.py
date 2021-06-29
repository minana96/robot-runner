import os
import pandas as pd
from datetime import datetime
from paramiko import SSHClient, AutoAddPolicy
from Plugins.Profilers.LogFileProfiler import LogFileProfiler
from ProgressManager.Output.OutputProcedure import OutputProcedure


class FindObject2dProfiler(LogFileProfiler):

    def __init__(self, ip_addr, username, hostname) -> None:
        super().__init__(ip_addr, username, hostname)

    def process_log_files(self, output_folder, find_object_2d_on_pc=True):
        ssh_client = None
        sftp_client = None
        find_object_2d_log_file = None
        obj_recognition_results_log_file = None

        # SSH to the remote machine
        try:
            ssh_client = SSHClient()
            ssh_client.load_host_keys(f"/home/{os.environ['USERNAME']}/.ssh/known_hosts")
            ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            ssh_client.connect(self.ip_addr, username=self.username)
            sftp_client = ssh_client.open_sftp()
            
            # If find_object_2d node is executed on this PC, fetch the log file locally
            if find_object_2d_on_pc:
                find_object_2d_log_file = self.open_local_log_file("find_object_2d")
            # Otherwise fetch the file over SFTP 
            else:
                find_object_2d_log_file = self.open_remote_log_file(ssh_client, sftp_client, "find_object_2d")

            # Process log file
            find_object_2d_df = self.process_find_object_2d_log_file(find_object_2d_log_file)

            # Fetch remotely and process obj_recognition_results log file
            obj_recognition_results_log_file = self.open_remote_log_file(ssh_client, sftp_client, "sherlock_obj_recognition")
            obj_recognition_results_df = self.process_obj_recognition_results(obj_recognition_results_log_file)

            # Calculate the delay of receiving the detection result at the side of obj_recognition_results node in ms
            find_object_2d_df['detection_received_at'] = obj_recognition_results_df['result_received']
            find_object_2d_df['result_delay_ms'] = find_object_2d_df['detection_received_at'] - find_object_2d_df['detection_ended_at']
            find_object_2d_df['result_delay_ms'] = find_object_2d_df['result_delay_ms'].apply(lambda x: x.total_seconds() * 1000)

            find_object_2d_df.to_csv(os.path.join(output_folder, "find_object_2d_results.csv"), index=False, header=True)
            OutputProcedure.console_log_OK("FindObject2d profiler done")

        except BaseException as e:
            OutputProcedure.console_log_FAIL("FindObject2d profiler failed!")
            print(e)
            
        finally:
            # Close all resources that are successfully open
            if find_object_2d_log_file:
                find_object_2d_log_file.close()

            if obj_recognition_results_log_file:
                obj_recognition_results_log_file.close()

            if sftp_client:
                sftp_client.close()

            if ssh_client:
                ssh_client.close()


    def process_find_object_2d_log_file(self, log_file):
        # Data to extract from the file
        data = {
            'frame_received_at': [], 
            'num_of_descriptors_extracted': [], 
            'extraction_time_ms': [],
            'detection_ended_at': [],
            'detection_time_ms': [],
            'id_of_detected_object': []
        }

        for line in log_file:
            # New frame received
            if 'Extracting descriptors from object -1...' in line:
                # Extract the receiving time of the frame
                line = line[line.index('(') + 1:line.index(')')]
                frame_received_at = datetime.strptime(line, '%Y-%m-%d %H:%M:%S.%f')

                data['frame_received_at'].append(frame_received_at)
            # Feature extraction
            elif 'descriptors extracted from object -1' in line:
                # Remove logging info
                line = line[line.index(')') + 2:]
                # Number of descriptrors
                num_of_descriptors = int(line[:line.index('descriptor')])
                data['num_of_descriptors_extracted'].append(num_of_descriptors)

                # Extraction time in ms
                extraction_time = int(line[line.index('in ') + 3 : line.index(' ms')])
                data['extraction_time_ms'].append(extraction_time)
            # Feature detection
            elif ('INFO' in line) and ('detected' in line):
                # Time when object is detected
                time_as_string = line[line.index('(') + 1:line.index(')')]
                detection_ended_at = datetime.strptime(time_as_string, '%Y-%m-%d %H:%M:%S.%f')
                data['detection_ended_at'].append(detection_ended_at)

                # Remove logging date and time 
                line = line[line.index(')') + 2:]
                # Remove time 
                line = line[line.index(')') + 2:]
                
                if 'No objects' in line:
                    object_detected = None
                else:
                    object_detected = int(line[line.index('Object ') + 7 : line.index('detected')])
                data['id_of_detected_object'].append(object_detected)

                # Detection time in ms
                detection_time = int(line[line.index('(') + 1 : line.index('ms')])    
                data['detection_time_ms'].append(detection_time)       

        return pd.DataFrame(data)


    def process_obj_recognition_results(self, log_file):
        data = {
            'result_received': []
        }

        for line in log_file:
            if '[rosout][INFO]' in line and 'detected' in line:
                time_received_string = line[line.index('[rosout][INFO] ') + len('[rosout][INFO] ') : line.rfind(':')]
                time_received = datetime.strptime(time_received_string, '%Y-%m-%d %H:%M:%S,%f')
                data['result_received'].append(time_received)

        return pd.DataFrame(data)

    def get_average_results(self, input_folder):
        input_file = os.path.join(input_folder, "find_object_2d_results.csv")
        results_df = pd.read_csv(input_file)
        recognition_ratio = results_df['id_of_detected_object'].count() / len(results_df['id_of_detected_object']) * 100
        return results_df['extraction_time_ms'].mean(), results_df['detection_time_ms'].mean(), results_df['result_delay_ms'].mean(), recognition_ratio


if __name__ == "__main__":
    fp = FindObject2dProfiler(ip_addr="192.168.1.7", username="ubuntu", hostname="ubuntu")
    fp.process_log_files("/home/milica/Desktop", find_object_2d_on_pc=False)