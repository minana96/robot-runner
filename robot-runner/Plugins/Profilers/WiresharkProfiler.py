import pyshark
import threading
import os
import pandas as pd
from ProgressManager.Output.OutputProcedure import OutputProcedure


class WiresharkProfiler:

    def __init__(self, network_interface, pc_ip_address, robot_ip_adress) -> None:
        self.network_interface = network_interface
        self.pc_ip_address = pc_ip_address
        self.robot_ip_adress = robot_ip_adress
        self.profiler_on = False
        self.network_thread = None
        self.data = None

    def start_measurement(self) -> None:
        # Dictionary for captured packets info
        self.data = {
            'timestamp': [], 
            'protocol': [], 
            'src_addr': [],
            'src_port': [],
            'dst_addr': [],
            'dst_port': [],
            'length_B': []
        }

        self.profiler_on = True
        self.network_thread = threading.Thread(target=self.capture_live_packets)
        self.network_thread.start()
        OutputProcedure.console_log_OK("Network profiler started")

    def stop_measurement(self, output_folder) -> None:
        self.profiler_on = False
        self.network_thread.join()

        # Save data frame in the file
        network_df = pd.DataFrame(self.data)
        network_df.to_csv(os.path.join(output_folder, "network.csv"), index=False, header=True)
        OutputProcedure.console_log_OK("Network profiler stopped")

    def capture_live_packets(self):
        # Start the live capture
        capture = pyshark.LiveCapture(interface=self.network_interface, display_filter=f"ip.addr=={self.pc_ip_address} && ip.addr=={self.robot_ip_adress}")
        
        # Sniff continuously until stop_measurement is called
        for raw_packet in capture.sniff_continuously():
            if not self.profiler_on:
                break

            if raw_packet:
                self.add_packet(raw_packet)
        
        capture.clear()
        capture.close()


    def add_packet(self, packet):
        try:
            # Parse details from the packed and save them in the data dictionary
            timestamp = packet.sniff_time
            protocol = packet.transport_layer
            src_addr = packet.ip.src
            src_port = packet[packet.transport_layer].srcport
            dst_addr = packet.ip.dst
            dst_port = packet[packet.transport_layer].dstport
            lenght_B = packet.length

            self.data['timestamp'].append(timestamp)
            self.data['protocol'].append(protocol)
            self.data['src_addr'].append(src_addr)
            self.data['src_port'].append(src_port)
            self.data['dst_addr'].append(dst_addr)
            self.data['dst_port'].append(dst_port)
            self.data['length_B'].append(lenght_B)
        except:
            OutputProcedure.console_log_FAIL("Error while processing a packet")
            print(packet)

    def get_total_results(self, input_folder):
        input_file = os.path.join(input_folder, "network.csv")
        results_df = pd.read_csv(input_file)
        return results_df['length_B'].count(), results_df['length_B'].sum()
        