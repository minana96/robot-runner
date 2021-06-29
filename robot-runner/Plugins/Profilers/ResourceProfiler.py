import subprocess
import os
from datetime import datetime
from ProgressManager.Output.OutputProcedure import OutputProcedure
import pandas as pd


class ResourceProfiler:

    def start_measurement(self):
        try:
            # Start the measurments
            start_resource_measurment_service_call = "rosservice call /start_resource_measurements"
            process = subprocess.run(start_resource_measurment_service_call.split(), check=True, capture_output=True, text=True)
            output = process.stdout
            print(output)
            #if output == "started: True\n":
            OutputProcedure.console_log_OK("Resource profiler started")
        except BaseException as e:
            OutputProcedure.console_log_FAIL("Error while starting resource profiler")
            print(e)

    def stop_measurement(self, output_dir):
        try:
            # Stop the measurement and save results into a file
            stop_resource_measurement_service_call = "rosservice call /stop_resource_measurements"
            process = subprocess.run(stop_resource_measurement_service_call.split(), check=True, capture_output=True, text=True)
            output = process.stdout
            #if output == "success: True\n":

            data = {
                'timestamp': [], 
                'cpu_util': [],
                'mem_util': []
            }

            timestamps = output[output.index('[') + 1 : output.index(']')].split(", ")
            data['timestamp'] = [datetime.fromtimestamp(int(x)/1000.0) for x in timestamps]

            output = output[output.index(']') + 1 :]

            cpu_util = output[output.index('[') + 1 : output.index(']')].split(", ")
            data["cpu_util"] = [float(x) for x in cpu_util]

            output = output[output.index(']') + 1 :]

            mem_util = output[output.index('[') + 1 : output.index(']')].split(", ")
            data["mem_util"] = [int(x) for x in mem_util]

            power_df = pd.DataFrame(data)
            power_df.to_csv(os.path.join(output_dir, "resources.csv"), index=False, header=True)

            OutputProcedure.console_log_OK("Resource profiler stopped")
        except BaseException as e:
            OutputProcedure.console_log_FAIL("Error while stoping resource profiler")
            print(e)


    def get_average_results(self, input_folder):
        input_file = os.path.join(input_folder, "resources.csv")
        results_df = pd.read_csv(input_file)
        return results_df['cpu_util'].mean(), results_df['mem_util'].mean()









