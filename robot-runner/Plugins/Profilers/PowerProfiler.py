import subprocess
import os
import pandas as pd
from ProgressManager.Output.OutputProcedure import OutputProcedure
from datetime import datetime, time


class PowerProfiler:

    def start_measurement(self):
        try:
            # Start the measurments
            start_resource_measurment_service_call = "rosservice call /start_ina219_measurement"
            process = subprocess.run(start_resource_measurment_service_call.split(), check=True, capture_output=True, text=True)
            output = process.stdout
            #if output == "started: True\n":
            OutputProcedure.console_log_OK("Power profiler started")
        except:
            OutputProcedure.console_log_FAIL("Error while starting power profiler")
            pass

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
        except:
            OutputProcedure.console_log_FAIL("Error while stoping power profiler")
            pass









