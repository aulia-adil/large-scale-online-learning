import json
import time
import mlflow
import mlflow.sklearn
from flask import Flask, logging, request, jsonify # 'logging' might be an issue if it's the standard module, consider 'app.logger'
import threading
from confluent_kafka import Producer
import logging as std_logging
import os


lock = threading.Lock()

# get ipaddr hostname -i
ipaddr = os.popen('hostname -i').read().strip()


app = Flask(__name__)

# Simple file logging setup
std_logging.basicConfig(
    filename=f'api_inference_{ipaddr}.log',
    level=std_logging.ERROR,  # Set to ERROR to reduce log noise
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Also log to console
console_handler = std_logging.StreamHandler()
console_handler.setLevel(std_logging.ERROR)  # Set to ERROR to reduce log noise
app.logger.addHandler(console_handler)

# It's good practice to initialize global vars to None or a default state
model = None
producer = None

@app.route('/predict', methods=['POST'])
def predict():
    global model, producer, feature_names

    if model is None:
        # Or handle more gracefully, e.g., by ensuring model is loaded first
        return jsonify({"error": "Model not loaded"}), 503
    if producer is None:
        return jsonify({"error": "Kafka producer not initialized"}), 503
    if feature_names is None:
        return jsonify({"error": "Feature names not set"}), 503

    data = request.get_json(force=True)
    raw_features = data[:-1]  # Exclude the last element which is the label
    app.logger.info(f'Received raw features for prediction: {raw_features}') # Use app.logger
    data_ground_truth = data[-1]  # The last element is the ground truth label

    # --- MODIFICATION START ---
    # You need to know the feature names your model expects.
    # If they are just generic names like "0", "1", "2", ... based on position:
    # IMPORTANT: Replace these with the actual feature names if they are different.
    # These names must match what the model was trained with.
    try:
        # Assuming the number of features is consistent.
        # If you know the exact feature names from training, use them directly:
        # feature_names = ["actual_feature_name_0", "actual_feature_name_1", ...]
        # num_features = len(raw_features)
        # feature_names = [str(i) for i in range(num_features)] # Generates ["0", "1", ..., "N-1"]

        data_for_prediction_dict = {name: value for name, value in zip(feature_names, raw_features)}
        app.logger.info(f'Formatted data for prediction (dict): {data_for_prediction_dict}')
    except Exception as e:
        app.logger.error(f"Error preparing features for prediction: {e}")
        return jsonify({"error": "Error preparing features"}), 400
    # --- MODIFICATION END ---

    try:
        y_pred_probas = model.predict_proba_one(data_for_prediction_dict) # Use the dictionary
        # y_pred_probas is usually a dict like {class_0_proba: 0.X, class_1_proba: 0.Y}
        # Assuming you want the probability of the positive class (class 1)
        # The structure of y_pred_probas depends on your River model and number of classes.
        # If it's binary classification, it might return probabilities for both classes.
        # For example: {0: 0.3, 1: 0.7}. You need to pick the one you need.
        # Let's assume y_pred_probas[1] gives the probability for the positive class.
        # Verify this based on your model's output.
        prediction_value = y_pred_probas.get(1, 0.0) # Safely get proba for class 1, default to 0.0 if not found
        app.logger.info(f'Prediction probabilities: {y_pred_probas}, Selected value for Kafka: {prediction_value}')

    except Exception as e:
        app.logger.error(f"Error during prediction: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"error": "Prediction failed"}), 500


    # Try to send to Kafka, but don't let it block the prediction response
    try:
        kafka_message = json.dumps([data, prediction_value]) # Send original data and the specific prediction
        producer.produce(
            topic="Update",
            key=str(time.time()).encode('utf-8'), # Kafka keys are often strings
            value=kafka_message.encode('utf-8'),
        )
        app.logger.info("Message sent to Kafka successfully")
    except Exception as e:
        app.logger.error(f'Failed to send message to Kafka: {e}')
        app.logger.info("Continuing with prediction response despite Kafka failure")
        # Skip Kafka sending and continue - don't retry or block the response

    return jsonify(prediction_value) # Return the specific prediction value

@app.teardown_appcontext
def flush_producer(error):
    global producer # Ensure you're referring to the global producer
    if producer:
        app.logger.info("Flushing Kafka producer on app context teardown.")
        producer.flush()

@app.route('/mlflow-uri', methods=['POST'])
def mlflow_uri_route(): # Renamed to avoid conflict with mlflow module
    mlflow_tracking_uri = request.get_json(force=True) # Use a more descriptive variable name
    app.logger.info(f"Receive MLflow URI: {mlflow_tracking_uri}")
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    return jsonify({"message": "MLflow URI set successfully", "uri": mlflow_tracking_uri})

@app.route('/kafka-uri', methods=['POST'])
def kafka_uri_route(): # Renamed for clarity
    global producer
    kafka_bootstrap_servers = request.get_json(force=True) # Use a more descriptive variable name
    app.logger.info(f"Receive Kafka URI: {kafka_bootstrap_servers}")
    try:
        producer = Producer({
            'bootstrap.servers': kafka_bootstrap_servers,
            "queue.buffering.max.messages": 100000000,
            # Add other producer configs as needed, e.g., error callbacks
            # 'error_cb': kafka_error_cb,
        })
        app.logger.info("Kafka producer initialized.")
    except Exception as e:
        app.logger.error(f"Failed to initialize Kafka producer: {e}")
        return jsonify({"error": f"Failed to initialize Kafka producer: {e}"}), 500
    return jsonify({"message": "Kafka producer initialized successfully", "uri": kafka_bootstrap_servers})

@app.route('/load', methods=['POST'])
def load_model_route(): # Renamed for clarity
    global model, lock, feature_names

    experiment_data = request.get_json(force=True)
    app.logger.info(f'Experiment data received: {experiment_data}')

    dataset_name = experiment_data[0].split('-')[0].strip() if isinstance(experiment_data, list) and len(experiment_data) > 0 else None
    if dataset_name == 'AGR_a' or dataset_name == 'AGR_g':
        feature_names = ['salary', 'commission', 'age', 'elevel', 'car', 'zipcode', 'hvalue', 'hyears', 'loan']
    elif dataset_name == 'youchoose':
        feature_names = ['sessionID', 'itemID', 'category', 'month', 'dayOfMonth', 'dayOfWeek', 'hour',
                         'differenceBetween2Dates', 'positionClickOnSession', 'sessaoComCompra',
                         'quantidadeClicksSessao', 'clicksProductSameSession', 'avgBetweenClicks', 'price',
                         'top100MaisVendidos', 'top100MaisVisualizados']


    if not isinstance(experiment_data, list) or len(experiment_data) < 2:
        return jsonify({"error": "Invalid experiment data format. Expected a list of [experiment_name, run_id]."}), 400

    experiment_name = experiment_data[0].strip()
    run_id = experiment_data[1].strip()
    app.logger.info(f"Attempting to load model from run_id: {run_id}, experiment_name: {experiment_name}")

    with lock:
        try:
            model_uri = f"runs:/{run_id}/{experiment_name}" # This usually refers to an artifact path within the run
            # For river models, you might have saved the model with a specific artifact path, e.g., "model" or "river_model"
            # If 'experiment_name' is indeed the artifact path for the model within the run:
            # model_uri = f"runs:/{run_id}/{experiment_name}"
            # Or if 'experiment_name' is the registered model name and 'run_id' is the version/stage:
            # model_uri = f"models:/{experiment_name}/{run_id}"
            # Clarify how you save your river model with MLflow.
            # Common practice is: runs:/<RUN_ID>/<ARTIFACT_PATH_TO_MODEL>
            # If 'experiment_name' is the name of the model artifact (e.g., "hoeffding_tree_model")
            # then model_uri = f"runs:/{run_id}/{experiment_name}" is correct IF 'experiment_name' is that artifact path.
            # If 'experiment_name' is truly the experiment's name, you might need to find the artifact path.
            # However, your previous structure implies 'experiment_name' is used as the artifact key.
            start_time = time.time()
            loaded_model = mlflow.sklearn.load_model(model_uri)
            end_time = time.time()
            with open(f'load_model_{ipaddr}.csv', 'a') as f:
                f.write(f"{experiment_name},{start_time},{end_time}\n")
            # Verify it's a River model if necessary, though mlflow.sklearn should handle it if saved correctly.
            model = loaded_model # Assign to global model
            app.logger.info(f'Model loaded successfully from: {model_uri}')
        except Exception as e:
            app.logger.error(f"Error loading model from {model_uri}: {e}")
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({"error": f"Failed to load model: {e}"}), 500

    return jsonify({"message": f"Model loaded successfully from URI: {model_uri}", "model_type": str(type(model))})


if __name__ == '__main__':
    # Set up Flask logging properly
    app.run(host='0.0.0.0', port=5001, debug=False)