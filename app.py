from flask import Flask, render_template, request, redirect, url_for, session, flash
from ldap3 import Server, Connection, ALL, NTLM
import os
from flask import jsonify

import serial.tools.list_ports
import json
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Load local users from a JSON file
def load_local_users():
    with open('users.json', 'r') as file:
        return json.load(file)

def list_com_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def authenticate(username, password):
    local_users = load_local_users()
    # Check for local user
    if username in local_users and local_users[username] == password:
        return True
    
    # Check for AD user
    server = Server('your_ad_server', get_info=ALL)
    conn = Connection(server, user=f'your_domain\\{username}', password=password, authentication=NTLM)
    if conn.bind():
        return True
    
    return False

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    com_ports = list_com_ports()
    return render_template('home.html', com_ports=com_ports, username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if authenticate(username, password):
            session['username'] = username
            session['show_welcome'] = True  
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')
@app.route('/check_welcome')
def check_welcome():
    show_welcome = session.pop('show_welcome', False)
    return jsonify({'show_welcome': show_welcome, 'username': session.get('username', '')})

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/about')
def about():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('about.html')

@app.route('/configure/<port>', methods=['GET', 'POST'])
def configure_port(port):
    if 'username' not in session:
        return redirect(url_for('login'))
    config_files = os.listdir('configs')
    output = None
    if request.method == 'POST':
        custom_commands = request.form['custom_commands']
        commands = custom_commands.split('\n')
        output = configure_switch(port, commands)
    return render_template('configure.html', port=port, config_files=config_files, output=output)

@app.route('/configure_all', methods=['GET', 'POST'])
def configure_all():
    if 'username' not in session:
        return redirect(url_for('login'))
    com_ports = list_com_ports()
    config_files = os.listdir('configs')
    output = None
    if request.method == 'POST':
        for port in com_ports:
            custom_commands = request.form[f'custom_commands_{port}']
            commands = custom_commands.split('\n')
            output = (output or "") + f"Configuring {port}:\n"
            output += configure_switch(port, commands)
            output += "\n"
    return render_template('configure_all.html', com_ports=com_ports, config_files=config_files, output=output)

def configure_switch(port, commands):
    result = []
    try:
        with serial.Serial(port, 9600, timeout=1) as ser:
            for command in commands:
                ser.write(command.encode() + b'\n')
                time.sleep(1)  
                while ser.in_waiting:
                    result.append(ser.readline().decode().strip())
    except Exception as e:
        result.append(f"Failed to configure {port}: {e}")
    return "\n".join(result)

@app.route('/edit_config/<filename>')
def edit_config(filename):
    if 'username' not in session:
        return redirect(url_for('login'))
    config_path = f'configs/{filename}'
    with open(config_path, 'r') as file:
        config_content = file.read()
    return config_content


if __name__ == '__main__':
    app.run(debug=True)
