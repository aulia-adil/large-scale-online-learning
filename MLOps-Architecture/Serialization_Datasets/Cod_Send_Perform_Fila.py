""" ------------------- Library Imports ------------------- """
import multiprocessing
import pandas as pd
import numpy as np
import time
import requests
import json
from sklearn.metrics import roc_auc_score
from confluent_kafka import Producer
from river import stream
import matplotlib.pyplot as plt
import csv
import os
import mlflow
import subprocess
import concurrent.futures
from multiprocessing import Pool
from multiprocessing import Process
import threading
import sys


""" 
    ["AGR_a_NB", "AGR_a.csv"],
    ["AGR_a_ARF", "AGR_a.csv"],
    ["AGR_a_HT", "AGR_a.csv"],
    ["AGR_a_SRP", "AGR_a.csv"],
    ["AGR_g_NB", "AGR_g.csv"],
    ["AGR_g_ARF", "AGR_g.csv"],
    ["AGR_g_HT", "AGR_g.csv"],
    ["AGR_g_SRP", "AGR_g.csv"],
    ["airlines_NB", "airlines.csv"],
    ["airlines_ARF", "airlines.csv"],
    ["airlines_HT", "airlines.csv"],
    ["airlines_SRP", "airlines.csv"],
    ["youchoose_NB", "youchoose.csv"], 
    ["youchoose_ARF", "youchoose.csv"],
    ["youchoose_HT", "youchoose.csv"],
    ["youchoose_SRP", "youchoose.csv"]  

    ["AGR_a_NB", "AGR_a.csv"],    
    ["AGR_a_ARF", "AGR_a.csv"],
    ["AGR_a_HT", "AGR_a.csv"],
    ["AGR_g_NB", "AGR_g.csv"],
    ["AGR_g_ARF", "AGR_g.csv"],
    ["AGR_g_HT", "AGR_g.csv"],
    ["youchoose_NB", "youchoose.csv"], 
    ["youchoose_ARF", "youchoose.csv"],
    ["youchoose_HT", "youchoose.csv"]
    
"""


experiments = [
    ["AGR_a_HT", "AGR_a.csv"],
    ["AGR_g_HT", "AGR_g.csv"]
]


pod_name_result = subprocess.run(["kubectl -n kafka get pods --no-headers -o name | grep kafka"], capture_output=True, text=True, shell=True)
pod_name = pod_name_result.stdout.replace('\n', '')
print(pod_name)

for ex in experiments:
    exp_name = ex[0]
    print(f'Experiment_Name: {exp_name}')

    """ ------------------- Variable Declarations ------------------- """
    df = pd.read_csv("datasets/csv/" + ex[1])
    name_df = ex[1]

    description = 'Predictive performance test'
    n_processes = 6
    shape_df = df.shape
    model_update_rate = 1500 #  --> --> -->    MODEL VERSIONING FREQUENCY    <-- <-- <-- <--

    manager = multiprocessing.Manager()
    df_queue = manager.Queue()
    [df_queue.put(record) for record in df.to_dict('records')]
        
    metric_rate = 1000
    time_data = manager.dict()
    metrics = manager.list()
    graph_data = manager.list()
    lag_list = manager.list()

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()

    kafka_bootstrap_servers = '10.32.2.213:32092'
    kafka_topic = 'Update'

    url = 'http://master:32001/predict'

    processes = []

    print(f'Serialization frequency: {model_update_rate}')

    """ ------------------- Configure Cluster IPs ------------------- """
    load_ips = []

    ips_out = subprocess.run(["kubectl get pods --no-headers -o custom-columns=':status.podIP' | grep 10.1.124"], capture_output=True, text=True, shell=True)
    ips = ips_out.stdout.split('\n')
    ips.remove('')
    active_pods_count = len(ips)
    for c in ips:
        load_ips.append(f'http://{c}:5001/load')

    url_pods = 'http://master:32002/pods'

    if active_pods_count == 1:
        r_pods = requests.post(url_pods,json=([load_ips[0]]))
    elif active_pods_count == 2:
        r_pods = requests.post(url_pods,json=(load_ips[0], load_ips[1]))
    elif active_pods_count == 3:
        r_pods = requests.post(url_pods,json=(load_ips[0], load_ips[1], load_ips[2]))
    elif active_pods_count == 4:
        r_pods = requests.post(url_pods,json=(load_ips[0], load_ips[1], load_ips[2], load_ips[3]))
    elif active_pods_count == 5:
        r_pods = requests.post(url_pods,json=(load_ips[0], load_ips[1], load_ips[2], load_ips[3], load_ips[4]))
    elif active_pods_count == 6:
        r_pods = requests.post(url_pods,json=(load_ips[0], load_ips[1], load_ips[2], load_ips[3], load_ips[4], load_ips[5]))
    elif active_pods_count == 7:
        r_pods = requests.post(url_pods,json=(load_ips[0], load_ips[1], load_ips[2], load_ips[3], load_ips[4], load_ips[5], load_ips[6]))
    elif active_pods_count == 8:
        r_pods = requests.post(url_pods,json=(load_ips[0], load_ips[1], load_ips[2], load_ips[3], load_ips[4], load_ips[5], load_ips[6], load_ips[7]))
    else:
        print('Error configuring number of pods')

    print(f'Number of active Pods: {active_pods_count}')


    """ ------------------- Configure Experiment ------------------- """
    url_load = 'http://master:32002/load'
    r_load = requests.post(url_load, json=(ex[0]))


    """ ------------------- Reset Counter ------------------- """
    url_count = 'http://master:32002/cont'
    r_count = requests.post(url_count, json=(0))


    """ ------------------- Configure Rate ------------------- """
    url_rate = 'http://master:32002/taxa'
    r_rate = requests.post(url_rate, json=(model_update_rate))
    

    """ ------------------- Cluster Information ------------------- """
    #- API Version Used -#
    list_version_infe = subprocess.run(["kubectl", "get", "deployment.apps/api-inferencia", "-o=jsonpath='{.spec.template.spec.containers[].image}'"], capture_output=True, text=True)
    api_version_infe = list_version_infe.stdout.split(':')[1][:-1]

    list_version_up = subprocess.run(["kubectl", "get", "deployment.apps/api-update", "-o=jsonpath='{.spec.template.spec.containers[].image}'"], capture_output=True, text=True)
    api_version_up = list_version_up.stdout.split(':')[1][:-1]

    list_replicas_infe = subprocess.run(["kubectl", "get", "deployment.apps/api-inferencia", "-o=jsonpath='{.spec.replicas}'"], capture_output=True, text=True)
    n_replicas_infe = int(list_replicas_infe.stdout[1])

    list_replicas_up = subprocess.run(["kubectl", "get", "deployment.apps/api-update", "-o=jsonpath='{.spec.replicas}'"], capture_output=True, text=True)
    n_replicas_up = int(list_replicas_up.stdout[1])

    list_cpu_infe = subprocess.run(["kubectl", "get", "deployment.apps/api-inferencia", "-o=jsonpath='{.spec.template.spec.containers[].resources.limits.cpu}'"], capture_output=True, text=True)
    CPU_limit_infe = list_cpu_infe.stdout

    list_cpu_up = subprocess.run(["kubectl", "get", "deployment.apps/api-update", "-o=jsonpath='{.spec.template.spec.containers[].resources.limits.cpu}'"], capture_output=True, text=True)
    CPU_limit_up = list_cpu_up.stdout


    """ ------------------- Function Declarations ------------------- """
    def get_lag(lag_list):
        global pod_name
        try:
            kubectl_command = ["kubectl", "exec", "-it", pod_name, "--namespace=kafka", "--", "kafka-consumer-groups.sh", "--bootstrap-server", "localhost:9092", "--describe", "--group", "update"]
            kubectl_output = subprocess.run(kubectl_command, capture_output=True, text=True)
            awk_command = ['awk', 'NR > 1 {sum += $6} END {print sum}']
            lag = subprocess.run(awk_command, input=kubectl_output.stdout, capture_output=True, text=True)
            lag_list.append(int(lag.stdout.strip()))
        except:
            lag_list.append(0)

    def performance(metrics, graph_data):
        global lock2
        y_true_list = []
        y_score_list = []

        with lock2:
            for i in metrics[-metric_rate:]:
                y_true_list.append(i[0])
                y_score_list.append(i[1])

            y_true = np.array(y_true_list)
            y_score = np.array(y_score_list)
            graph_data.append(round(roc_auc_score(y_true, y_score), 4))
            #print(f'Graph Length: {len(graph_data)}')

    def inf(t, queue, time_data, metrics, graph_data, lag_list):
        global metric_rate, kafka_bootstrap_servers, kafka_topic
        producer = Producer({'bootstrap.servers': kafka_bootstrap_servers, "queue.buffering.max.messages": 100000000})
        while not queue.empty():
            try:
                X = queue.get()
                y = X.popitem()
                r = s.post(url, json=(X))
                metrics.append([y[1], r.json()])

                if len(metrics) % metric_rate == 0:
                    performance(metrics, graph_data)
                    threading.Thread(target=get_lag, args=(lag_list,)).start()

                json_message = json.dumps([X, y[1]])
                producer.produce(kafka_topic, key=None, value=json_message.encode('utf-8'))
            except multiprocessing.TimeoutError:
                pass  # Queue is empty, continue
            except:
                break
            #print(f'Queue Length: {queue.qsize()}')
        producer.flush()
        time_data[t] = (time.time())


    """ ------------------- Process Start ------------------- """
    print(f'Running Experiment {exp_name}...')

    s = requests.Session()

    start_time = time.time()

    for i in range(n_processes):
        process = multiprocessing.Process(target=inf, args=(f't{i+1}', df_queue, time_data, metrics, graph_data, lag_list))
        processes.append(process)
        process.start()

        # Wait until all processes finish or the queue is empty
    #while any(process.is_alive() for process in processes) or not df_queue.empty():
    while not df_queue.empty():
        time.sleep(2)
        
    time.sleep(1)

    for process in processes:
        process.terminate()  # Manually terminate processes

    s.close()
    
    """ ------------------- Checking Kafka Queue Status ------------------- """
    print('Checking remaining time to consume queue')
    kubectl_command = ["kubectl", "exec", "-it", pod_name, "--namespace=kafka", "--", "kafka-consumer-groups.sh", "--bootstrap-server", "localhost:9092", "--describe", "--group", "update"]
    kubectl_output = subprocess.run(kubectl_command, capture_output=True, text=True)
    awk_command = ['awk', 'NR > 1 {sum += $6} END {print sum}']
    lag = subprocess.run(awk_command, input=kubectl_output.stdout, capture_output=True, text=True)
    queue_status = int(lag.stdout.strip())
    while queue_status != 0:
        kubectl_output = subprocess.run(kubectl_command, capture_output=True, text=True)
        awk_command = ['awk', 'NR > 1 {sum += $6} END {print sum}']
        lag = subprocess.run(awk_command, input=kubectl_output.stdout, capture_output=True, text=True)
        queue_status = int(lag.stdout.strip())    
        if queue_status > 20000:
            time.sleep(40)
        else:
            time.sleep(10)

    end_total_time = time.time()


    """ ------------------- Prepare Logs for Recording ------------------- """
    n_df, _ = name_df.split('.')
    total_instances_count = len(metrics)
    time_records = {}
    time_list = []

    for i in time_data:
        time_records[i] = (time_data[i] - start_time)
        time_list.append(time_data[i] - start_time)

    avg_time = round(sum(time_list)/len(time_list), 4)
    total_consumption_time = round(end_total_time - start_time, 4)

    # Exp_Performance_Queue.csv
    path = 'arq_logs/logs_exp_preform/Exp_Perf_Preditiva_Por_Endpoints_2.csv'
    isFile = os.path.isfile(path)

    if isFile:
        line_count = subprocess.run(["wc", "-l", "arq_logs/logs_exp_preform/Exp_Perf_Preditiva_Por_Endpoints_2.csv"], capture_output=True, text=True)
        n_lines, _ = line_count.stdout.split(' ')
        id_lines = f'Exp-{n_lines}'
    else:
        id_lines = 'Exp-1'


    """ ------------------- Create Columns ------------------- """
    header = [
        "id",
        "api_version_infe",
        "api_version_up",
        "exp_name",
        "name_df",
        "n_endpoints_infe",
        "n_endpoints_up",
        "cpu_limit_infe",
        "cpu_limit_up",
        "shape_df",
        "n_processes",
        "total_instances_count",
        "model_update_frequency",
        "metric_evolution",
        "kafka_queue",
        "inference_process_times",
        "avg_inference_time",
        "total_consumption_time",
        "description"
    ]

    logs = [
        f'{id_lines}',
        api_version_infe,
        api_version_up,
        exp_name,
        name_df,
        n_replicas_infe,
        n_replicas_up,
        CPU_limit_infe,
        CPU_limit_up,
        shape_df,
        n_processes,
        total_instances_count,
        model_update_rate,
        graph_data,
        lag_list,
        time_records,
        avg_time,
        total_consumption_time,
        description
    ]


    """ ------------------- Record Experiment Logs ------------------- """
    if isFile:
        with open(path, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(logs)
    else:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(header)
            w.writerow(logs)
    f.close()
    print(f'Recording of {id_lines} OK')
    print(60*'_')

    time.sleep(2)