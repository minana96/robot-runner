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

    def __init__(self):
        """Executes immediately after program start, on config load"""
        self.find_object_2d_profiler = FindObject2dProfiler(ip_addr="192.168.1.7", username="ubuntu", hostname="ubuntu")
        self.camera_client = None        

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
                #FactorModel("example_factor", ['example_treatment1', 'example_treatment2']),
                FactorModel("runs_per_variation", range(1, 4))
            ]
        )
        run_table.create_experiment_run_table()
        return run_table.get_experiment_run_table()

    def start_run(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for starting the run here. 
        Activities before and after starting the run should also be performed here."""

        print("Config.start_run() called!")

        # SSH to the robot
        self.camera_client = SSHClient()
        self.camera_client.load_host_keys("/home/milica/.ssh/known_hosts")
        self.camera_client.set_missing_host_key_policy(AutoAddPolicy())
        self.camera_client.connect("192.168.1.7", username="ubuntu")

        # Launch the camera
        stdin, stdout, ststderr = self.camera_client.exec_command("roslaunch raspicam_node camerav2_1280x960.launch", get_pty = True)

        # Wait for the camera to start recording
        for line in iter(stdout.readline, ""):
            print(line, end = "")
            if "Video capture started" in line:
                break
        
        # Outputs and inputs to this session are not needed anymore
        stdin.close()
        stdout.close()
        ststderr.close()

    def start_measurement(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        print("Config.start_measurement called!")

    def launch_mission(self, context: RobotRunnerContext) -> None:
        """Perform any activity interacting with the robotic
        system in question (simulated or real-life) here."""

        print("Config.launch_mission() called!")

        # SSH to the robot
        mission_client = SSHClient()
        mission_client.load_host_keys("/home/milica/.ssh/known_hosts")
        mission_client.set_missing_host_key_policy(AutoAddPolicy())
        mission_client.connect("192.168.1.7", username="ubuntu")

        # Launch the mission
        stdin, stdout, stderr = mission_client.exec_command("roslaunch sherlock raspi_obj_recognition.launch", get_pty = True)
        
        # Print all otputs of the mission as it progresses
        for line in iter(stdout.readline, ""):
            print(line, end = "")

        # Wait for the mission to end
        exit_status = stdout.channel.recv_exit_status()
        print(50*"=")

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
        self.find_object_2d_profiler.process_log_files(context.run_dir.absolute())

    def stop_run(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for stopping the run here.
        Activities before and after stopping the run should also be performed here."""
        
        print("Config.stop_run() called!")

        # Stop the SSH connection to camera
        self.camera_client.close()
        print(50*"=")
        print("Camera stopped")
    
    def populate_run_data(self, context: RobotRunnerContext) -> tuple:
        """Return the run data as a row for the output manager represented as a tuple"""
        return None

    # ===============================================DO NOT ALTER BELOW THIS LINE=================================================
    # NOTE: Do not alter these values
    experiment_path:            Path             = None
