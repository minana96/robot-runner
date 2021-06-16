import pyshark
import threading
import os
import pandas as pd


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
            'length (B)': []
        }

        self.profiler_on = True
        self.network_thread = threading.Thread(target=self.capture_live_packets)
        self.network_thread.start()
        print("Network profiler started")

    def stop_measurement(self, output_folder) -> None:
        self.profiler_on = False
        self.network_thread.join()

        # Save data frame in the file
        network_df = pd.DataFrame(self.data)
        network_df.to_csv(os.path.join(output_folder, "network.csv"), index=False, header=True)
        print("Network profiler stopped")

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
        # Parse details from the packed and save them in the data dictionary
        self.data['timestamp'].append(packet.sniff_time)
        self.data['protocol'].append(packet.transport_layer)
        self.data['src_addr'].append(packet.ip.src)
        self.data['src_port'].append(packet[packet.transport_layer].srcport)
        self.data['dst_addr'].append(packet.ip.dst)
        self.data['dst_port'].append(packet[packet.transport_layer].dstport)
        self.data['length (B)'].append(packet.length)
        