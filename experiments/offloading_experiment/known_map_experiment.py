from EventManager.Models.RobotRunnerEvents import RobotRunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RobotRunnerContext import RobotRunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ProgressManager.Output.OutputProcedure import OutputProcedure

import time
from typing import Dict, List
from pathlib import Path
from paramiko import SSHClient, AutoAddPolicy

from Plugins.Profilers.FindObject2dProfiler import FindObject2dProfiler
from Plugins.Profilers.MoveBaseProfiler import MoveBaseProfiler
from Plugins.Profilers.PowerProfiler import PowerProfiler
from Plugins.Profilers.ResourceProfiler import ResourceProfiler
from Plugins.Profilers.WiresharkProfiler import WiresharkProfiler


class RobotRunnerConfig:
    # =================================================USER SPECIFIC NECESSARY CONFIG=================================================
    # Name for this experiment
    name:                       str             = "known_map_experiment"
    # Required ROS version for this experiment to be ran with 
    # NOTE: (e.g. ROS2 foxy or eloquent)
    # NOTE: version: 2
    # NOTE: distro: "foxy"
    required_ros_version:       int             = 1
    required_ros_distro:        str             = "melodic"
    # Experiment operation types
    operation_type:             OperationType   = OperationType.SEMI
    # Run settings
    time_between_runs_in_ms:    int             = 60000
    # Path to store results at
    # NOTE: Path does not need to exist, will be appended with 'name' as specified in this config and created on runtime
    results_output_path:        Path             = Path("~/experiment_results")
    # =================================================USER SPECIFIC UNNECESSARY CONFIG===============================================

    # NOTE: Required configurations for experiment replication
    robot_ip_addr:              str              = "192.168.1.7"
    robot_username:             str              = "ubuntu"
    robot_hostname:             str              = "ubuntu"
    pc_ip_address:              str              = "192.168.1.9"
    network_interface_used:     str              = "wlp0s20f3"
    ssh_host_key_dir:           str              = "/home/milica/.ssh/known_hosts"

    # Profilers used in the experiment
    find_object_2d_profiler:    FindObject2dProfiler
    move_base_profiler:         MoveBaseProfiler
    network_profiler:           WiresharkProfiler
    resource_profiler:          ResourceProfiler
    power_profiler:             PowerProfiler

    def __init__(self):
        """Executes immediately after program start, on config load"""
        self.find_object_2d_profiler = FindObject2dProfiler(ip_addr=self.robot_ip_addr, username=self.robot_username, hostname=self.robot_hostname)
        self.move_base_profiler = MoveBaseProfiler(ip_addr=self.robot_ip_addr, username=self.robot_username, hostname=self.robot_hostname)
        self.network_profiler = WiresharkProfiler(network_interface=self.network_interface_used, pc_ip_address=self.pc_ip_address, robot_ip_adress=self.robot_ip_addr)
        self.resource_profiler = ResourceProfiler()
        self.power_profiler = PowerProfiler()
        self.startup_client = None     
        self.mission_start_timestamp = None
        self.mission_end_timestamp = None   

        EventSubscriptionController.subscribe_to_multiple_events([ 
            (RobotRunnerEvents.START_RUN,           self.start_run),
            (RobotRunnerEvents.START_MEASUREMENT,   self.start_measurement),
            (RobotRunnerEvents.LAUNCH_MISSION,      self.launch_mission),
            (RobotRunnerEvents.STOP_MEASUREMENT,    self.stop_measurement),
            (RobotRunnerEvents.STOP_RUN,            self.stop_run),
            (RobotRunnerEvents.CONTINUE,            self.signal_continue),
            (RobotRunnerEvents.POPULATE_RUN_DATA,   self.populate_run_data)
        ])
        
        print("Custom config loaded")

    def create_run_table(self) -> List[Dict]:
        """Create and return the run_table here. A run_table is a List (rows) of tuples (columns), 
        representing each run robot-runner must perform"""
        run_table = RunTableModel(
            factors = [
                FactorModel("amcl_offloaded", ['false', 'true']),
                FactorModel("navigation_offloaded", ['false', 'true']),
                FactorModel("obj_recognition_offloaded", ['false', 'true'])
            ],
            data_columns=[
                'mission_execution_s',
                'avg_extraction_time_ms', 
                'avg_detection_time_ms', 
                'avg_detection_result_delay_ms',
                'recognition_ratio',
                'avg_goal_sending_delay_ms', 
                'avg_goal_processing_s',
                'avg_nav_result_delay_ms',
                'num_of_packets', 
                'size_of_packets', 
                'avg_cpu_util', 
                'avg_memory_util',
                'energy_J'
            ],
            num_of_repetitions=10,
            randomize_order=True
        )
        run_table.create_experiment_run_table()
        return run_table.get_experiment_run_table()

    def start_run(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for starting the run here. 
        Activities before and after starting the run should also be performed here."""

        # SSH to the robot
        self.startup_client = SSHClient()
        self.startup_client.load_host_keys(self.ssh_host_key_dir)
        self.startup_client.set_missing_host_key_policy(AutoAddPolicy())
        self.startup_client.connect(self.robot_ip_addr, username=self.robot_username)

        # Launch camera and profilers
        stdin, stdout, ststderr = self.startup_client.exec_command(f"roslaunch sherlock start_up.launch frequency:=50", get_pty = True)

        turtlebot_ready = False
        camera_ready = False
        resource_profiler_ready = False
        power_profiler_ready = False
        obj_recognition_results_ready = False

        # Wait for the robot, camera and profilers to be ready
        for line in iter(stdout.readline, ""):
            print(line, end = "")

            if "Calibration End" in line:
                turtlebot_ready = True
            if "Video capture started" in line:
                camera_ready = True
            if "Resource profiler ready" in line:
                resource_profiler_ready = True
            if "Initialised connection with INA219 board" in line:
                power_profiler_ready = True
            if "SherlockObjRecognition results subscriber started" in line:
                obj_recognition_results_ready = True

            if turtlebot_ready and camera_ready and resource_profiler_ready and power_profiler_ready and obj_recognition_results_ready:
                break        
        
        # Outputs and inputs to this session are not needed anymore
        stdin.close()
        stdout.close()
        ststderr.close()

    def start_measurement(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for starting measurements."""

        self.power_profiler.start_measurement()
        self.resource_profiler.start_measurement()
        self.network_profiler.start_measurement()

    def launch_mission(self, context: RobotRunnerContext) -> None:
        """Perform any activity interacting with the robotic
        system in question (simulated or real-life) here."""
        variation = context.run_variation
        OutputProcedure.console_log_bold(f"AMCL offloaded               = {variation['amcl_offloaded']}")
        OutputProcedure.console_log_bold(f"Navigation offloaded         = {variation['navigation_offloaded']}")
        OutputProcedure.console_log_bold(f"Object recognition offloaded = {variation['obj_recognition_offloaded']}")
        

        # SSH to the robot
        mission_client = SSHClient()
        mission_client.load_host_keys(self.ssh_host_key_dir)
        mission_client.set_missing_host_key_policy(AutoAddPolicy())
        mission_client.connect(self.robot_ip_addr, username=self.robot_username)

        # Pass the parameter to the launch file if object recognition is offloaded or not
        amcl_offloaded =  context.run_variation['amcl_offloaded']
        navigation_offloaded =  context.run_variation['navigation_offloaded']
        obj_recognition_offloaded =  context.run_variation['obj_recognition_offloaded']
        
        # Launch the mission
        self.mission_start_timestamp = time.time()
        stdin, stdout, stderr = mission_client.exec_command(f"roslaunch sherlock known_map.launch offload_amcl:={amcl_offloaded} offload_navigation:={navigation_offloaded} offload_obj_recognition:={obj_recognition_offloaded}", get_pty = True)
        
        # Print all otputs of the mission as it progresses
        for line in iter(stdout.readline, ""):
            print(line, end = "")

        # Wait for the mission to end
        exit_status = stdout.channel.recv_exit_status()
        self.mission_end_timestamp = time.time()
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

        run_dir = context.run_dir.absolute()

        self.network_profiler.stop_measurement(run_dir)
        self.resource_profiler.stop_measurement(run_dir)
        self.power_profiler.stop_measurement(run_dir)

        # Pass the information if find_object_2d is offloaded or not to the log reader
        obj_recognition_offloaded = (context.run_variation['obj_recognition_offloaded'] == "true")
        self.find_object_2d_profiler.process_log_files(run_dir, obj_recognition_offloaded)

        # Pass the information if move_base is offloaded or not to the log reader
        navigation_offloaded = (context.run_variation['navigation_offloaded'] == "true")
        self.move_base_profiler.process_log_files(run_dir, navigation_offloaded)

    def stop_run(self, context: RobotRunnerContext) -> None:
        """Perform any activity required for stopping the run here.
        Activities before and after stopping the run should also be performed here."""
    
        # Stop the SSH connection
        self.startup_client.close()
        print(70*"=")
        print("Robot, camera and profilers stopped")

    def signal_continue(self) -> None:
        input('\n\n>> Press ENTER when you change the battery. <<\n\n')
    
    def populate_run_data(self, context: RobotRunnerContext) -> tuple:
        """Return the run data as a row for the output manager represented as a tuple"""
        variation = context.run_variation
        run_dir = context.run_dir.absolute()

        # Total execution time of the mission
        variation['mission_execution_s'] = self.mission_end_timestamp - self.mission_start_timestamp
        
        # Get averaged results from find_object_2d profiler
        avg_extraction_time, avg_detection_time, avg_detection_result_delay, recognition_ratio = self.find_object_2d_profiler.get_average_results(run_dir)
        variation['avg_extraction_time_ms'] = avg_extraction_time
        variation['avg_detection_time_ms'] = avg_detection_time
        variation['avg_detection_result_delay_ms'] = avg_detection_result_delay
        variation['recognition_ratio'] = recognition_ratio

        # Get averaged results from move_base profiler
        avg_goal_sending_delay_ms, avg_goal_processing_s, avg_nav_result_delay_ms = self.move_base_profiler.get_average_results(run_dir)
        variation['avg_goal_sending_delay_ms'] = avg_goal_sending_delay_ms
        variation['avg_goal_processing_s'] = avg_goal_processing_s
        variation['avg_nav_result_delay_ms'] = avg_nav_result_delay_ms       

        # Get averaged results from wireshark profiler
        num_of_packets, size_of_packets = self.network_profiler.get_total_results(run_dir)
        variation['num_of_packets'] = num_of_packets
        variation['size_of_packets'] = size_of_packets

        # Get averaged results form resource profiler
        avg_cpu_util, avg_memory_util = self.resource_profiler.get_average_results(run_dir)
        variation['avg_cpu_util'] = avg_cpu_util
        variation['avg_memory_util'] = avg_memory_util

        # Get averaged results from power profiler
        energy = self.power_profiler.get_total_results(run_dir)
        variation['energy_J'] = energy

        return variation

    # ===============================================DO NOT ALTER BELOW THIS LINE=================================================
    # NOTE: Do not alter these values
    experiment_path:            Path             = None
