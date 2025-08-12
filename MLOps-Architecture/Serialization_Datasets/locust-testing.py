import subprocess
import threading
import time
from locust import HttpUser, task, between
import csv
import json # Assuming your data and response are JSON

import csv
from multiprocessing import Queue
import multiprocessing
from confluent_kafka import Producer
import pandas as pd

import time
import json
import statistics
from confluent_kafka import Producer
from locust import User, task, events, between
from locust import constant

'''
manager = multiprocessing.Manager()
    df_queue = manager.Queue()
    [df_queue.put(record) for record in df.to_dict('records')]
'''

import csv
import threading
from locust import HttpUser, task, between

class SequentialDatasetReader:
    """
    Thread-safe sequential dataset reader for concurrent virtual users.
    Ensures each record is processed exactly once in original sequence.
    """
    def __init__(self, dataset_path, cycle=True):
        """
        Initialize the dataset reader.
        
        Args:
            dataset_path: Path to the CSV dataset file
            cycle: If True, restart from beginning when dataset is exhausted
        """
        self.dataset_path = dataset_path
        self.cycle = cycle
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        self.data = []
        self.current_index = 0
        self._load_data()
    
    def _load_data(self):
        """Load all dataset records into memory."""
        df = pd.read_csv(self.dataset_path)
        self.data = [row.tolist() for _, row in df.iterrows()]
            
        if not self.data:
            raise ValueError("Dataset is empty")
    
    def get_next_record(self):
        """
        Thread-safely get the next record from the dataset.
        
        Returns:
            The next record as a dictionary, or None if dataset is exhausted and cycle=False
        """
        with self.lock:
            # Check if we've reached the end
            if self.current_index >= len(self.data):
                if not self.cycle:
                    return None
                # Reset to beginning if cycling
                self.current_index = 0
            
            # Get the next record and increment the counter
            record = self.data[self.current_index]
            self.current_index += 1
            return record

# Global shared instance for all virtual users
dataset_reader = None

def init_dataset(dataset_path, cycle=True):
    """Initialize the global dataset reader."""
    global dataset_reader
    dataset_reader = SequentialDatasetReader(dataset_path, cycle)
    return dataset_reader     

host1 = "http://34.133.6.92:32001"
# --- Locust User Class ---
class MLPredictionUser(HttpUser):
    host = host1
    wait_time = constant(0)

    @task
    def make_prediction_request(self):
        # prediction_endpoint_path = "/predict"
        
        X = dataset_reader.get_next_record()
        # print(f"Processing record {X}")
        if X is None:
            print("Dataset exhausted. Stopping the experiment.")
            self.environment.runner.quit()
            return
        self.client.post(f"{self.host}/predict", json=X)
        
dataset_dir = "Datasets/real_usage/"
file_name = "AGR_a_real_test.csv"
DATASET_PATH = dataset_dir + file_name


init_dataset(DATASET_PATH, cycle=False)  # Set cycle=False if you want to stop when dataset is exhausted
print("Dataset initialized")
    