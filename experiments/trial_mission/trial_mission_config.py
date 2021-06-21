from EventManager.Models.RobotRunnerEvents import RobotRunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RobotRunnerContext import RobotRunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType

from typing import Dict, List
from pathlib import Path
from paramiko import SSHClient, AutoAddPolicy

from Plugins.Profilers.FindObject2dProfiler import FindObject2dProfiler
from Plugins.Profilers.PowerProfiler import PowerProfiler
from Plugins.Profilers.ResourceProfiler import ResourceProfiler
from Plugins.Profilers.WiresharkProfiler import WiresharkProfiler


class RobotRunnerConfig:
    # =================================================USER SPECIFIC NECESSARY CONFIG=================================================
    # Name for this experiment
    name:                       str             = "trial_mission"
    # Required ROS version for this experiment to be ran with 
    # NOTE: (e.g. ROS2 foxy or eloquent)
    # NOTE: version: 2
    # NOTE: distro: "foxy"
    required_ros_version:       int             = 1
    required_ros_distro:        str             = "melodic"
    # Experiment operation types
    operation_type:             OperationType   = OperationType.SEMI
    # Run settings
    time_between_runs_in_ms:    int             = 10000
    # Path to store results at
    # NOTE: Path does not need to exist, will be appended with 'name' as specified in this config and created on runtime
    results_output_path:        Path             = Path("~/experiment_results")
    # =================================================USER SPECIFIC UNNECESSARY CONFIG===============================================

    # Dynamic configurations can be one-time satisfied here before the program takes the config as-is
    # NOTE: Setting some variable based on some criteria
    find_object_2d_profiler: FindObject2dProfiler
    network_profiler: WiresharkProfiler
    resource_profiler: ResourceProfiler
    power_profiler: PowerProfiler

    def __init__(self):
        """Executes immediately after program start, on config load"""
        self.find_object_2d_profiler = FindObject2dProfiler(ip_addr="192.168.1.7", username="ubuntu", hostname="ubuntu")
        self.network_profiler = WiresharkProfiler(network_interface='wlp0s20f3', pc_ip_address="192.168.1.9", robot_ip_adress="192.168.1.7")
        self.resource_profiler = ResourceProfiler()
        self.power_profiler = PowerProfiler()
        self.startup_client = None        

        EventSubscriptionController.subscribe_to_multiple_events([ 
            (RobotRunnerEvents.START_RUN,           self.start_run),
            (RobotRunnerEvents.START_MEASUREMENT,   self.start_measurement),
            (RobotRunnerEvents.LAUNCH_MISSION,      self.launch_mission),
            (RobotRunnerEvents.STOP_MEASUREMENT,    self.stop_measurement),
            (RobotRunnerEvents.STOP_RUN,            self.stop_run),
            (RobotRunnerEvents.POPULATE_RUN_DATA,   self.populate_run_data)
        ])
        
        print("Custom config loaded")

    def create_run_table(self) -> List[Dict]:
        """Create and return the run_table here. A run_table is a List (rows) of tuples (columns), 
        representing each run robot-runner must perform"""
        run_table = RunTableModel(
            factors = [
                FactorModel("obj_recognition_offloaded", ['false', 'true']),
                #FactorModel("runs_per_variation", range(1, 4))
            ],
            data_columns=['avg_extraction_time', 'avg_detection_time', 'avg_result_delay', 'num_of_packets', 'size_of_packets', 'avg_cpu_util', 'avg_memory_util']
        )
        run_table.create_experiment_run_table()
        return run_table.get_experiment_run_table()

    def start_run(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for starting the run here. 
        Activities before and after starting the run should also be performed here."""

        print("Config.start_run() called!")

        # SSH to the robot
        self.startup_client = SSHClient()
        self.startup_client.load_host_keys("/home/milica/.ssh/known_hosts")
        self.startup_client.set_missing_host_key_policy(AutoAddPolicy())
        self.startup_client.connect("192.168.1.7", username="ubuntu")

        # Launch camera and profilers
        stdin, stdout, ststderr = self.startup_client.exec_command("roslaunch sherlock raspi_startup.launch", get_pty = True)

        camera_ready = False
        resource_profiler_ready = False
        power_profiler_ready = False

        # Wait for the camera and profiler to be ready
        for line in iter(stdout.readline, ""):
            print(line, end = "")

            if "Video capture started" in line:
                camera_ready = True
            if "Resource profiler ready" in line:
                resource_profiler_ready = True
            if "Initialised connection with INA219 board" in line:
                power_profiler_ready = True

            if camera_ready and resource_profiler_ready and power_profiler_ready:
                break        
        
        # Outputs and inputs to this session are not needed anymore
        stdin.close()
        stdout.close()
        ststderr.close()

    def start_measurement(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        print("Config.start_measurement called!")
        self.resource_profiler.start_measurement()
        self.power_profiler.start_measurement()
        self.network_profiler.start_measurement()

    def launch_mission(self, context: RobotRunnerContext) -> None:
        """Perform any activity interacting with the robotic
        system in question (simulated or real-life) here."""

        print("Config.launch_mission() called!")

        # SSH to the robot
        mission_client = SSHClient()
        mission_client.load_host_keys("/home/milica/.ssh/known_hosts")
        mission_client.set_missing_host_key_policy(AutoAddPolicy())
        mission_client.connect("192.168.1.7", username="ubuntu")

        # Pass the parameter to the launch file if object recognition is offloaded or not
        obj_recognition_offloaded =  context.run_variation['obj_recognition_offloaded']
        
        # Launch the mission
        stdin, stdout, stderr = mission_client.exec_command(f"roslaunch sherlock raspi_obj_recognition.launch offload:={obj_recognition_offloaded}", get_pty = True)
        
        # Print all otputs of the mission as it progresses
        for line in iter(stdout.readline, ""):
            print(line, end = "")

        # Wait for the mission to end
        exit_status = stdout.channel.recv_exit_status()
        print(70*"=")

        if exit_status == 0:
            print('Mission ended successfully!')
        else:
            print('ERROR DURING MISSION!!!')

        # Close SSH session
        stdin.close()
        stdout.close()
        stderr.close()
        mission_client.close()

    def stop_measurement(self, context: RobotRunnerContext) -> None:
        """Perform any activity here required for stopping measurements."""
        print("Config.stop_measurement called!")
        run_dir = context.run_dir.absolute()
        self.network_profiler.stop_measurement(run_dir)
        self.power_profiler.stop_measurement(run_dir)
        self.resource_profiler.stop_measurement(run_dir)

        # Pass the information if find_object_2d is offloaded or not to the log reader
        obj_recognition_offloaded = (context.run_variation['obj_recognition_offloaded'] == "true")
        self.find_object_2d_profiler.process_log_files(run_dir, obj_recognition_offloaded)

    def stop_run(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for stopping the run here.
        Activities before and after stopping the run should also be performed here."""
        
        print("Config.stop_run() called!")

        # Stop the SSH connection to camera
        self.startup_client.close()
        print(70*"=")
        print("Camera and profiler stopped")
    
    def populate_run_data(self, context: RobotRunnerContext) -> tuple:
        """Return the run data as a row for the output manager represented as a tuple"""
        variation = context.run_variation
        run_folder = context.run_dir.absolute()
        
        # Get averaged results from find_object_2d profiler
        avg_extraction_time, avg_detection_time, avg_result_delay = self.find_object_2d_profiler.get_average_results(run_folder)
        variation['avg_extraction_time'] = avg_extraction_time
        variation['avg_detection_time'] = avg_detection_time
        variation['avg_result_delay'] = avg_result_delay

        # Get averaged results from wireshark profiler
        num_of_packets, size_of_packets = self.network_profiler.get_total_results(run_folder)
        variation['num_of_packets'] = num_of_packets
        variation['size_of_packets'] = size_of_packets

        # Get averaged results form resource profiler
        avg_cpu_util, avg_memory_util = self.resource_profiler.get_total_results(run_folder)
        variation['avg_cpu_util'] = avg_cpu_util
        variation['avg_memory_util'] = avg_memory_util

        return variation

    # ===============================================DO NOT ALTER BELOW THIS LINE=================================================
    # NOTE: Do not alter these values
    experiment_path:            Path             = None
