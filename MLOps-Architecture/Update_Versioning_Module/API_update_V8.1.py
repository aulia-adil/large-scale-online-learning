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

# Declaration of variables
counter = 0
load_rate = 1000

lock = threading.Lock()

consumer = None

# Model serialization function
def save(model):
    global experiment_name, list_pods, model_version, current_datetime

    mlflow.set_experiment(experiment_name)
    model_version += 1
    run_name = f"{current_datetime}_{model_version}"
    with mlflow.start_run(run_name=run_name):
        mlflow.sklearn.log_model(model,
                                 artifact_path=experiment_name,
                                 )
        run_id = mlflow.active_run().info.run_id
    for pod in list_pods:
        r = requests.post(pod, json=([experiment_name, run_id]))
        print(f"Response from pod {pod}: {r.text}")


app = Flask(__name__)

# Main function
def update():
    global counter, model, load_rate, consumer

    print("Starting update thread...")
    # loads data from the request and separates into X and y
    for message in consumer:
        data = json.loads(message.value)
        Xi = (data[0])
        yi = (data[1])
        print(f"Received data: {Xi}, {yi}")
        try:
            model = model.learn_one(Xi, yi)
        except:
            pass
        counter += 1

        if counter % load_rate == 0:
            Process(target=save, args=(model,)).start()

@app.route('/rate', methods=['POST'])
def rate():
    global load_rate
    load_rate = request.get_json(force=True)
    print(f"Receive load rate: {load_rate}")
    return jsonify(load_rate)

@app.route('/mlflow-uri', methods=['POST'])
def mlflow_uri():
    mlflow_uri = request.get_json(force=True)
    print(f"Receive MLflow URI: {mlflow_uri}")
    mlflow.set_tracking_uri(mlflow_uri)
    return jsonify(mlflow_uri)

@app.route('/kafka-uri', methods=['POST'])
def kafka_uri():
    global consumer
    kafka_uri = request.get_json(force=True)
    print(f"Receive kafka URI: {kafka_uri}")
    consumer = KafkaConsumer(
        'Update',
        bootstrap_servers= kafka_uri,
        group_id='update',
        auto_offset_reset='latest',
        api_version=(0, 10, 1)
    )
    threading.Thread(target=update).start()   
    return jsonify(kafka_uri)

@app.route('/count', methods=['POST'])
def count():
    global counter
    counter = request.get_json(force=True)
    print(f"Receive counter: {counter}")
    return jsonify(counter)

@app.route('/pods', methods=['POST'])
def pods():
    global list_pods
    list_pods = request.get_json(force=True)
    print(f"List of pods: {list_pods}")
    return jsonify(list_pods)

@app.route('/load', methods=['POST'])
def load():
    global model, lock, experiment_name, model_version, list_pods, current_datetime
    
    
    experiment_name = request.get_json(force=True)
    classifier = experiment_name.split("-")[1]

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


    model_version = 0

    with lock:
        mlflow.set_experiment(experiment_name)
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_name = f"{current_datetime}_{model_version}"
        with mlflow.start_run(run_name=run_name):
            mlflow.sklearn.log_model(model,
                                     artifact_path=experiment_name,
                                     )
            run_id = mlflow.active_run().info.run_id
        for pod in list_pods:
            r = requests.post(pod, json=([experiment_name, run_id]))
            print(f"Response from pod {pod}: {r.text}")

    return jsonify(f'Succeed to load model: {model}')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)