import time
import board
import busio
import adafruit_adxl34x
import RPi.GPIO as GPIO
import multiprocessing
import csv
import paho.mqtt.client as mqtt
import json
import numpy as np
from scipy import fftpack

SAMPLE_NUMBER = 10000

def is_adxl345(accelerometer):
    return accelerometer._read_register_unpacked(0x00)&0xFF == 0xE5

def config_adxl345(accelerometer, x_offset, y_offset, z_offset):
    accelerometer.data_rate = adafruit_adxl34x.DataRate.RATE_800_HZ
    accelerometer.range = adafruit_adxl34x.Range.RANGE_16_G
    accelerometer._write_register_byte(0x1E, x_offset)
    accelerometer._write_register_byte(0x1F, y_offset)
    accelerometer._write_register_byte(0x20, z_offset)

def create_process(cb):
    pipe_r, pipe_w = multiprocessing.Pipe(False)
    proc = multiprocessing.Process(target = cb, args=(pipe_r,))
    return proc, pipe_w    
    
    
def proc_file(receive):
    arr = []
    i = 0
    file_num = 1
    while True:
        arr.append(receive.recv())
        i += 1
        if (i == SAMPLE_NUMBER):
            with open("data_.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(arr)
                i = 0
                file_num += 1
                arr = []
        

def proc_server(receive):
    THINGSBOARD_HOST = 'demo.thingsboard.io'
    ACCESS_TOKEN='J13IFXDuDR7KX9Yxh3Vt'
    sensor_data = {'Freq1':0,'Freq2':0,'Freq3':0}
    client = mqtt.Client()
    client.username_pw_set(ACCESS_TOKEN)
    client.connect(THINGSBOARD_HOST, 1883, 60)
    client.loop_start()
    arr_x = []
    arr_y = []
    arr_z = []
    i = 0
    vdc_x = 0
    vdc_y = 0
    vdc_z = 0
    while True:
        (x, y, z) = receive.recv()
        arr_x.append(x)
        arr_y.append(y)
        arr_z.append(z)
        vdc_x += x
        vdc_y += y
        vdc_z += z
        i += 1
        if (i == SAMPLE_NUMBER):
            vdc_x /= SAMPLE_NUMBER
            vdc_y /= SAMPLE_NUMBER
            vdc_z /= SAMPLE_NUMBER
            for i in range(SAMPLE_NUMBER):
                arr_x[i] -= vdc_x
                arr_y[i] -= vdc_y
                arr_z[i] -= vdc_z
            x_fft=fftpack.fft(arr_x)
            y_fft=fftpack.fft(arr_y)
            z_fft=fftpack.fft(arr_z)
            power_x = np.abs(x_fft)
            power_y = np.abs(y_fft)
            power_z = np.abs(z_fft)
            sample_freq_x = fftpack.fftfreq(len(arr_x), d=0.00125)      
            sample_freq_y = fftpack.fftfreq(len(arr_y), d=0.00125)
            sample_freq_z = fftpack.fftfreq(len(arr_z), d=0.00125)
            pos_mask_x = np.where(sample_freq_x > 0)
            pos_mask_y = np.where(sample_freq_y > 0)
            pos_mask_z = np.where(sample_freq_z > 0)
            freqs_x = sample_freq_x[pos_mask_x]
            freqs_y = sample_freq_y[pos_mask_y]
            freqs_z = sample_freq_z[pos_mask_z]
            x_max_idx = power_x[pos_mask_x].argsort()[-3:][::-1]
            y_max_idx = power_y[pos_mask_y].argsort()[-3:][::-1]
            z_max_idx = power_z[pos_mask_z].argsort()[-3:][::-1]
            x_max_1 = freqs_x[x_max_idx[0]] 
            x_max_2 = freqs_x[x_max_idx[1]] 
            x_max_3 = freqs_x[x_max_idx[2]] 
            y_max_1 = freqs_y[y_max_idx[0]] 
            y_max_2 = freqs_y[y_max_idx[1]] 
            y_max_3 = freqs_y[y_max_idx[2]] 
            z_max_1 = freqs_z[z_max_idx[0]] 
            z_max_2 = freqs_z[z_max_idx[1]] 
            z_max_3 = freqs_z[z_max_idx[2]] 
            sensor_data["Freq1"] = x_max_1
            sensor_data["Freq2"] = y_max_1
            sensor_data["Freq3"] = z_max_1
            print("--------------------")
            print(x_max_1)
            print(y_max_1)
            print(z_max_1)
            client.publish('v1/devices/me/telemetry', json.dumps(sensor_data), 1)
            arr_x = []
            arr_y = []
            arr_z = []
            vdc_x = 0
            vdc_y = 0
            vdc_z = 0
            i = 0

if __name__ == "__main__":
    file_proc, file_send = create_process(proc_file)
    server_proc, server_send = create_process(proc_server)

    file_proc.start()
    server_proc.start()


    i2c = busio.I2C(board.SCL, board.SDA)
    accelerometer = adafruit_adxl34x.ADXL345(i2c)
    if is_adxl345(accelerometer):
        config_adxl345(accelerometer, 45, 39, 142) # X_OFFSET Y_OFFSET Z_OFFSET

        try:
            while True:
                data = accelerometer.acceleration
                #print("interrupt %f %f %f" %data)
                file_send.send(data)
                server_send.send(data)
                time.sleep(0.001)
        except KeyboardInterrupt:
            for i in arr:
                print(i)

