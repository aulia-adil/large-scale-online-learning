import mlflow
import mlflow.sklearn
from flask import Flask, request, jsonify
import threading
import mlflow.sklearn
import requests
from kafka import KafkaConsumer
import json
from multiprocessing import Process
from datetime import datetime
from river import tree
from river import ensemble
from river import naive_bayes
from river import drift
import river
import time
import pandas as pd
from urllib.parse import urlparse
import logging as std_logging


# Declaration of variables
counter = 0
load_rate = 1000

lock = threading.Lock()

consumer = None

app = Flask(__name__)

# Simple file logging setup
std_logging.basicConfig(
    filename='api_update.log',
    level=std_logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Also log to console
console_handler = std_logging.StreamHandler()
console_handler.setLevel(std_logging.DEBUG)
app.logger.addHandler(console_handler)

# Model serialization function
def save(model):
    global experiment_name, list_pods, model_version, current_datetime

    mlflow.set_experiment(experiment_name)
    model_version += 1
    run_name = f"{current_datetime}_{model_version}"
    with mlflow.start_run(run_name=run_name):
        start_time = time.time()
        mlflow.sklearn.log_model(model,
                                 artifact_path=experiment_name,
                                 )
        end_time = time.time()
        with open("model_upload_latency.csv", "a") as f:
            f.write(f"{experiment_name},{start_time},{end_time}\n")
        run_id = mlflow.active_run().info.run_id
    for pod in list_pods:
        try:
            r = requests.post(pod, json=([experiment_name, run_id]), timeout=10)
            app.logger.info(f"Response from pod {pod}: {r.text}")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Failed to send data to pod {pod}: {e}")
        except Exception as e:
            app.logger.error(f"Unexpected error sending data to pod {pod}: {e}")

# Main function
def update():
    global counter, model, load_rate, consumer

    app.logger.info("Starting update thread...")
    # loads data from the request and separates into X and y
    for message in consumer:
        # Save message key and value to CSV with timestamp
        timestamp = time.time()
        message_key = message.key.decode('utf-8') if message.key else None
        message_value = message.value.decode('utf-8')
        
        with open("message_log.csv", "a") as f:
            f.write(f"{timestamp},{message_key},{message_value}\n")


        data = json.loads(message.value)
        Xi = (data[0][:-1])  # Exclude the last element which is the label
        yi = data[0][-1]  # The last element is the label
        predicted_result = (data[1])
        app.logger.info(f"Received data: {Xi}, {yi}")
        Xi = dict(zip(
            ['salary', 'commission', 'age', 'elevel', 'car', 'zipcode', 'hvalue', 'hyears', 'loan'],
            Xi
        ))
        try:
            model.learn_one(Xi, yi)
        except:
            # Print stacktrace
            print("Error learning from data:", Xi, yi)
            pass
        counter += 1

        if counter % load_rate == 0:
            Process(target=save, args=(model,)).start()
        with open("for_auc.csv", "a") as f:
            f.write(f"{time.time()},{yi},{predicted_result}\n")

@app.route('/rate', methods=['POST'])
def rate():
    global load_rate
    load_rate = int(request.get_json(force=True))
    # print(f"Receive load rate: {load_rate}")
    app.logger.info(f"Receive load rate: {load_rate}")
    return jsonify(load_rate)

@app.route('/mlflow-uri', methods=['POST'])
def mlflow_uri():
    global list_pods
    mlflow_uri = request.get_json(force=True)
    # print(f"Receive MLflow URI: {mlflow_uri}")
    app.logger.info(f"Receive MLflow URI: {mlflow_uri}")
    mlflow.set_tracking_uri(mlflow_uri)
    for pod in list_pods:
        try:
            # Clean the pod URL to extract the host (remove protocol and path)
            parsed_url = urlparse(pod)
            host = parsed_url.hostname
            inf_mlflow_uri = f"http://{host}:5001/mlflow-uri"
            r = requests.post(inf_mlflow_uri, json=(mlflow_uri), timeout=5)
            # print(f"Response from pod {inf_mlflow_uri}: {r.text}")
            app.logger.info(f"Response from pod {inf_mlflow_uri}: {r.text}")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Failed to send MLflow URI to pod {inf_mlflow_uri}: {e}")
        except Exception as e:
            app.logger.error(f"Unexpected error sending MLflow URI to pod {inf_mlflow_uri}: {e}")
    return jsonify(mlflow_uri)

@app.route('/kafka-uri', methods=['POST'])
def kafka_uri():
    global consumer, list_pods
    kafka_uri = request.get_json(force=True)
    # print(f"Receive kafka URI: {kafka_uri}")
    app.logger.info(f"Receive kafka URI: {kafka_uri}")
    consumer = KafkaConsumer(
        'Update',
        bootstrap_servers= kafka_uri,
        group_id='Update',
        auto_offset_reset='latest',
        api_version=(0, 10, 1)
    )
    threading.Thread(target=update).start()   
    for pod in list_pods:
        try:
            # Clean the pod URL to extract the host (remove protocol and path)
            parsed_url = urlparse(pod)
            host = parsed_url.hostname
            inf_kafka_uri = f"http://{host}:5001/kafka-uri"
            r = requests.post(inf_kafka_uri, json=(kafka_uri), timeout=10)
            # print(f"Response from pod {inf_kafka_uri}: {r.text}")
            app.logger.info(f"Response from pod {inf_kafka_uri}: {r.text}")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Failed to send Kafka URI to pod {inf_kafka_uri}: {e}")
        except Exception as e:
            app.logger.error(f"Unexpected error sending Kafka URI to pod {inf_kafka_uri}: {e}")
    return jsonify(kafka_uri)

@app.route('/count', methods=['POST'])
def count():
    global counter
    counter = int(request.get_json(force=True))
    # print(f"Receive counter: {counter}")
    app.logger.info(f"Receive counter: {counter}")
    return jsonify(counter)

@app.route('/pods', methods=['POST'])
def pods():
    global list_pods
    list_pods = request.get_json(force=True)
    # print(f"List of pods: {list_pods}")
    app.logger.info(f"List of pods: {list_pods}")
    return jsonify(list_pods)

@app.route('/load', methods=['POST'])
def load():
    global model, lock, experiment_name, model_version, list_pods, current_datetime
    
    
    experiment_name = request.get_json(force=True)
    dataset_name = experiment_name.split("-")[0]
    classifier = experiment_name.split("-")[1]
    # print(f"Dataset: {dataset_name}, Classifier: {classifier}")
    app.logger.info(f"Dataset: {dataset_name}, Classifier: {classifier}")

    if dataset_name == "AGR_a":
        df = pd.read_csv("AGR_a_first_train.csv")
    elif dataset_name == "AGR_g":
        df = pd.read_csv("AGR_g_first_train.csv")
    elif dataset_name == "youchoose":
        df = pd.read_csv("youchoose_first_train.csv")


    if classifier == "NB":
        model = river.naive_bayes.GaussianNB()
    elif classifier == "HT":
        model = river.tree.HoeffdingTreeClassifier(
            grace_period=200, 
            split_criterion='info_gain', 
            max_size=100
        )
    elif classifier == "ARF":
        model = river.ensemble.AdaptiveRandomForestClassifier(
            n_models=10, 
            drift_detector=river.drift.ADWIN(),
            split_criterion='info_gain'
        )
    elif classifier == "AB":
        model = river.ensemble.AdaBoostClassifier(
            model=river.tree.HoeffdingTreeClassifier(split_criterion='gini'),
            n_models=5
        )
    else:
        raise ValueError(f"Unknown classifier: {classifier}")
    # print river version
    print(f"River version: {river.__version__}")
    for index, row in df.iterrows():
        Xi = row[:-1].to_dict()
        yi = row[-1]
        try:
            model = model.learn_one(Xi, yi)
        except Exception as e:
            # print(f"Error learning from row {index}: {e}")
            app.logger.error(f"Error learning from row {index}: {e}")

    model_version = 0

    with lock:
        mlflow.set_experiment(experiment_name)
        current_datetime = str(int(time.time() * 1000))
        run_name = f"{current_datetime}_{model_version}"
        with mlflow.start_run(run_name=run_name):
            mlflow.sklearn.log_model(model,
                                     artifact_path=experiment_name,
                                     )
            run_id = mlflow.active_run().info.run_id
        for pod in list_pods:
            try:
                r = requests.post(pod, json=([experiment_name, run_id]), timeout=5)
                # print(f"Response from pod {pod}: {r.text}")
                app.logger.info(f"Response from pod {pod}: {r.text}")
            except requests.exceptions.RequestException as e:
                app.logger.error(f"Failed to send model data to pod {pod}: {e}")
            except Exception as e:
                app.logger.error(f"Unexpected error sending model data to pod {pod}: {e}")

    return jsonify(f'Succeed to load model: {model}')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)