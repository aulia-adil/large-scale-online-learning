import subprocess
import threading
import time
import csv
import os


def get_kafka_pod_name():
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", "kafka", "-o", "jsonpath={.items[0].metadata.name}"],
            capture_output=True, text=True, check=True
        )
        pod_name = result.stdout.strip()
        if not pod_name:
            print("No Kafka pods found in the 'kafka' namespace.")
        return pod_name
    except subprocess.CalledProcessError as e:
        print("Failed to get Kafka pod name:", e)
        return ""
    

def check_kafka_lag(consumer_group_name=None, parse_output=True):
    """Check Kafka consumer lag with optional parsing"""
    kafka_name = get_kafka_pod_name()
    if not kafka_name:
        print("No Kafka pod found. Cannot check lag.")
        return
    try:
        if consumer_group_name:
            # Check specific consumer group
            result = subprocess.run([
                "kubectl", "exec", kafka_name, "-n", "kafka", "--",
                "/opt/bitnami/kafka/bin/kafka-consumer-groups.sh",
                "--bootstrap-server", "localhost:9092",
                "--group", consumer_group_name,
                "--describe"
            ], capture_output=True, text=True, check=True)
        else:
            # List all consumer groups first
            result = subprocess.run([
                "kubectl", "exec", kafka_name, "-n", "kafka", "--",
                "/opt/bitnami/kafka/bin/kafka-consumer-groups.sh",
                "--bootstrap-server", "localhost:9092",
                "--list"
            ], capture_output=True, text=True, check=True)
        
        # print("Raw Output:")
        # print(result.stdout)
        
        # Parse the output if it's a consumer group description
        if consumer_group_name and parse_output:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                # Skip header line and process data lines
                for line in lines[1:]:
                    if line.strip() and not line.startswith('GROUP'):
                        parts = line.split()
                        if len(parts) >= 6:
                            group, topic, partition, current_offset, end_offset, lag = parts[:6]
                            # print(f"\n📊 LAG ANALYSIS:")
                            # print(f"Group: {group}")
                            # print(f"Topic: {topic}")
                            # print(f"Partition: {partition}")
                            # print(f"Current Offset: {current_offset}")
                            # print(f"End Offset: {end_offset}")
                            # print(f"LAG: {lag}")
                            
                            # Status interpretation
                            lag_value = int(lag)
                            # Save lag and timestamp to CSV
                            with open("kafka_lag_log.csv", "a", newline="") as csvfile:
                                writer = csv.writer(csvfile)
                                writer.writerow([time.time(), lag_value])
                            
        
        if result.stderr:
            print("Errors:", result.stderr)
            
    except subprocess.CalledProcessError as e:
        print(f"Error checking Kafka lag: {e}")
        print(f"stderr: {e.stderr}")

stop_event = threading.Event()

def run_kafka_lag_check_periodically(interval=60):
    def periodic_check():
        check_kafka_lag("Update")
        threading.Timer(interval, periodic_check).start()
    periodic_check()

run_kafka_lag_check_periodically(60)