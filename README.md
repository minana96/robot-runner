# Experiment Orchestration Tool for Evaluation of Computation Offloading Strategies in Robotic Systems

Robot Runner (RR) is a tool for automatic execution of measurement-based experiments on robotics software. For further details about the tool itself, the reader is reffered to [this](https://github.com/S2-group/robot-runner) GitHub repository, from which this repository is forked from and adjusted for the purpose of evaluation of the effect that computation offloading strageies have on the performance and energy consumption of ROS based systems. The guidelines for experiment replication and RR configuration are given below.

## Setup guide

### ROS configuration
The robot used in the experiment is [TurtleBot3 Burger](https://emanual.robotis.com/docs/en/platform/turtlebot3/overview/), whereas the experiment orchestraction is conducted from the PC via RR. Both TurtleBot3 and the PC need to run **Ubuntu 18.04** and they both need to have **ROS Melodic** installed (installation instructions are provided in [this](http://wiki.ros.org/melodic/Installation/Ubuntu) guide). TurtleBot3 and the PC need to be connected to the same local network, with the robot being set as a ROS master (i.e., running the *roscore* node). To that end, the following lines need to be added to the *.bashrc* file on the TurtleBot3:
```bash
export ROS_MASTER_URI=http://<TurtleBot3_IP_address>:11311
export ROS_HOSTNAME=<TurtleBot3_IP_address>
```
It is **important** that these two lines, along with the other ROS environment variables, are added to the very **fist lines** of the *.bashrc* file in TurtleBot3. Otherwise, the environment variables in *.bashrc* file will not be exported when ROS files are launched on the robot via SSH from the RR on PC. Conversly, the following lines need to be added to the *.bashrc* file on the PC:
```bash
export ROS_MASTER_URI=http://<TurtleBot3_IP_address>:11311
export ROS_HOSTNAME=<PC_IP_address>
```

### Time synchronisation

The times on the PC and the robot need to be syncronised with [chrony](https://chrony.tuxfamily.org/), which can be installed on both machines via `sudo apt install chrony`. The PC needs to be configured as an NTP server, whereas the robot is an NTP client. The configuration file located in `/etc/chrony/chrony.conf` on PC needs to be configured as follows:
```bash
local stratum 8
allow <TurtleBot3_IP_address>
```
Conversly, the configuration file in `/etc/chrony/chrony.conf` on the robot needs to be configured as follows:
```bash
server <PC_IP_address> minpoll 0 maxpoll 5 maxdelay .03
```

### Python configuration

This entire repository, that contains the configured RR experiment orchestration tool, needs to be cloned to the PC. RR is run with Python version 3.8, within a dedicated virtual environment. The following pip packages need to be installed: **tabulate**, **paramiko** and **pyshark** (based on *tshark*, which needs to be installed via `sudo apt install tshark`). Finally, the Python3.8 module *multiprocessing* needs to be supported by the system.

### ROS packages

The *sherlock* ROS package, that encapsulates the robotic mission under experimentation, is located in [this](https://github.com/minana96/sherlock) GitHub repository. The mission is launched on the TurtleBot3 and the reader is reffered to *sherlock* repository for further details on the mission itself. Since *sherlock* ROS package runs on the TurtleBot3, it does not need to be installed on the PC. ROS launch files contained in this package are run via SSH from the RR, thus *sherlock* package needs to installed only on the TurtleBot3.

The ROS package that needs to be configured on the PC is *ros_profilers_msgs*. The package source code and configuration instructions are provided in [this](https://github.com/minana96/ros_profilers_msgs) repository. This package contains ROS service definitions, for service calls made by two profilers (details in next section).

# Profilers

Profilers for collecting several metrics are implemented for the purpose of this experiment, but there are no restrictions to their broader usage in other experiments as well. The profilers can be added as plugins to RR and their source code is located in `robot-runner/Plugins/Profilers/` directory in this repository. The profilers and their purpose are as follows:
- **PowerProfiler.py**: the profiler for power consumption measurements. It starts and stops power consumption measurement via ROS service calls, where it acts as a service client. The service server is a ROS node contained in *ros_melodic_profilers* package, which needs to run on the robot itself. For the details on how to configure the service server, the reader is referred to the *ros_melodic_profilers* GitHub repository [here](https://github.com/minana96/ros_melodic_profilers);
- **ResourceProfiler.py**: the profiler for CPU usage and RAM utilisation measurements. It starts and stops the measurement via ROS service calls, where it acts as a service client. The service server is a ROS node contained in *ros_melodic_profilers* package, which needs to run on the robot itself. For the details on how to configure the service server, the reader is referred to the *ros_melodic_profilers* GitHub repository [here](https://github.com/minana96/ros_melodic_profilers);
- **WiresharkProfiler.py**: the profiler that captures network traffic exchanged between the robot and the PC. It records information about the timestamp of each network packet, the network protocol, its source and destination IP adress, source and destination port, and the packet size;
- **LogFileProfiler.py**: the abstract profiler that represents the base class for profilers that processes ROS log files of concrete ROS nodes. It provides unviersal methods for fetching ROS log files of nodes that run either locally or remotely;
- **FindObject2dProfiler.py**: the concrete log file profiler that parses information about feature extraction time, object detection time and detection result delay;
- **MoveBaseProfiler.py**: the concrete log file profiler that parses information about the delay for transmission of the navigation goal, the total navigation time and the delay for transmission of the navigation outcome.

# Experiment configuration files

The configuration files for orhestration of eight different experiments conducted in this study are located in `experiments/offloading_experiment/` directory in this repository. The configuration files and the experiment purposes are as follows:
- **unknown_map_experiment.py**: configuration file of the experiment that evaluates the effect of computation offloading strategies on performance and energy efficiency of ROS-based systems. 
To that aim, SLAM, navigation and object recognition are either offloaded or executed on-board the robot. The tasks are implemented in [gmapping](http://wiki.ros.org/gmapping), [move_base](http://wiki.ros.org/move_base) and [find_object_2d](http://wiki.ros.org/find_object_2d) ROS packages, respectfully;
- **known_map_experiment.py**: configuration file of the experiment that evaluates the effect of computation offloading strategies on performance and energy efficiency of ROS-based systems. 
To that aim, localisation, navigation and object recognition are either offloaded or executed on-board the robot. The tasks are implemented in [amcl](http://wiki.ros.org/amcl), [move_base](http://wiki.ros.org/move_base) and [find_object_2d](http://wiki.ros.org/find_object_2d) ROS packages, respectfully;
- **resolution_effect.py**: configuration file of the experiment that evaluates the effect of *image resolution* parameter on performance and energy efficiency of ROS-based systems;
- **frame_rate_effect.py**: configuration file of the experiment that evaluates the effect of *image frame rate* parameter on performance and energy efficiency of ROS-based systems;
- **particles_effect.py**: configuration file of the experiment that evaluates the effect of *particles* parameter in *gmapping* on performance and energy efficiency of ROS-based systems;
- **temporal_updates_effect.py**: configuration file of the experiment that evaluates the effect of *temporalUpdate* parameter in *gmapping* on performance and energy efficiency of ROS-based systems;
- **velocity_samples_effect.py**: configuration file of the experiment that evaluates the effect of *vx_samples* and *vth_samples* parameters in *local_planner* plugin in *move_base* (implemented in [dwa_local_planner](http://wiki.ros.org/dwa_local_planner) ROS package) on performance and energy efficiency of ROS-based systems;
- **sim_time_effect.py**: configuration file of the experiment that evaluates the effect of *sim_time* parameter in *local_planner* plugin in *move_base* (implemented in [dwa_local_planner](http://wiki.ros.org/dwa_local_planner) ROS package) on performance and energy efficiency of ROS-based systems.

The automated experiment execution can be initiated with the following comands, with `<experiment configuration file>` representing one of the Python files above:
```bash
cd <location of this cloned repository>
python robot-runner/ experiments/offloading_experiment/<experiment configuration file>
```

During replication, it is important that the noted values are adjusted to their respictive configuration (e.g., robot's IP adress, hostname, username). The values are noted in global variables section of all configuration files.
