import subprocess
import os
import numpy
import pandas as pd
from ProgressManager.Output.OutputProcedure import OutputProcedure
from datetime import datetime


class PowerProfiler:

    def start_measurement(self):
        try:
            # Start the measurments
            start_resource_measurment_service_call = "rosservice call /start_ina219_measurement"
            process = subprocess.run(start_resource_measurment_service_call.split(), check=True, capture_output=True, text=True)
            output = process.stdout
            #if output == "started: True\n":
            OutputProcedure.console_log_OK("Power profiler started")
        except BaseException as e:
            OutputProcedure.console_log_FAIL("Error while starting power profiler")
            print(e)

    def stop_measurement(self, output_dir):
        try:
            # Stop the measurement and save results into a file
            stop_resource_measurement_service_call = "rosservice call /stop_ina219_measurement"
            process = subprocess.run(stop_resource_measurement_service_call.split(), check=True, capture_output=True, text=True)
            output = process.stdout

            data = {
                'timestamp': [], 
                'power_mW': []
            }

            timestamps = output[output.index('[') + 1 : output.index(']')].split(", ")
            data['timestamp'] = [datetime.fromtimestamp(int(x)/1000.0) for x in timestamps]

            output = output[output.index(']') + 1 :]

            power = output[output.index('[') + 1 : output.index(']')].split(", ")
            data["power_mW"] = [float(x) for x in power]

            power_df = pd.DataFrame(data)
            power_df.to_csv(os.path.join(output_dir, "power.csv"), index=False, header=True)

            OutputProcedure.console_log_OK("Power profiler stopped")
        except BaseException as e:
            OutputProcedure.console_log_FAIL("Error while stoping power profiler")
            print(e)

    def get_total_results(self, input_folder):
        input_file = os.path.join(input_folder, "power.csv")
        results_df = pd.read_csv(input_file)
        timestamps_in_sec = [datetime.strptime(x, '%Y-%m-%d %H:%M:%S.%f').timestamp() for x in results_df['timestamp']]

        # Results in J 
        return numpy.trapz(results_df['power_mW'], x=timestamps_in_sec) / 1000


