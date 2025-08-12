import json
import time
import mlflow
import mlflow.sklearn
from flask import Flask, logging, request, jsonify
import threading
from confluent_kafka import Producer

lock = threading.Lock()

app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    global model, producer

    data = request.get_json(force=True)

    y_pred = model.predict_proba_one(data)

    kafka_message = json.dumps([data, y_pred[1]])

    try:
        producer.produce(
            topic="update",
            key=time.time(),
            value=kafka_message.encode('utf-8'),
        )
        # Don't flush after every message - let it batch
        producer.flush()
        
    except Exception as e:
        logging.error(f'Failed to produce message: {e}')
        # Handle the error appropriately

    return jsonify(y_pred[1])

# Add periodic flush or flush on shutdown
@app.teardown_appcontext
def flush_producer(error):
    if producer:
        producer.flush()

@app.route('/mlflow-uri', methods=['POST'])
def mlflow_uri():
    mlflow_uri = request.get_json(force=True)
    print(f"Receive MLflow URI: {mlflow_uri}")
    mlflow.set_tracking_uri(mlflow_uri)
    return jsonify(mlflow_uri)

@app.route('/kafka-uri', methods=['POST'])
def kafka_uri():
    global producer
    kafka_uri = request.get_json(force=True)
    print(f"Receive kafka URI: {kafka_uri}")
    producer = Producer({'bootstrap.servers': kafka_uri,  "queue.buffering.max.messages": 100000000}) 
    return jsonify(kafka_uri)

@app.route('/load', methods=['POST'])
def load():
    global model, lock

    experiment_data = request.get_json(force=True)
    print(f'Experiment: {experiment_data}')

    experiment_name = experiment_data[0]
    run_id = experiment_data[1]

    with lock:
        model_uri = f"runs:/{run_id}/{experiment_name}"
        model = mlflow.sklearn.load_model(model_uri)
        print(f'Model loaded from: {model_uri}')

    return jsonify(f'model: {model}')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
