import paramiko

def check_evolution():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to casaos.lan...")
        client.connect('casaos.lan', username='root', password='Malhi542', timeout=10)
        print("Connected.")
        
        print("Running: docker ps -a | grep -i evolution")
        stdin, stdout, stderr = client.exec_command('docker ps -a | grep -i evolution')
        out = stdout.read().decode()
        err = stderr.read().decode()
        print("STDOUT:", out)
        if err:
            print("STDERR:", err)
            
        lines = out.strip().split('\n')
        if lines and lines[0]:
            container_name = lines[0].split()[-1]
            container_id = lines[0].split()[0]
            print(f"Fetching logs for container {container_name} ({container_id})...")
            
            # Check resource usage just in case
            stdin, stdout, stderr = client.exec_command(f'docker stats --no-stream {container_id}')
            print("STATS:\n", stdout.read().decode())
            
            stdin, stdout, stderr = client.exec_command(f'docker logs --tail 100 {container_id}')
            logs_out = stdout.read().decode()
            logs_err = stderr.read().decode()
            if logs_out:
                print("LOGS STDOUT:\n", logs_out[-2000:])
            if logs_err:
                print("LOGS STDERR:\n", logs_err[-2000:])
        else:
            print("No container matching 'evolution' found. Let's list all containers just in case:")
            stdin, stdout, stderr = client.exec_command('docker ps -a')
            print("ALL CONTAINERS:", stdout.read().decode())
            
    except Exception as e:
        print("Error:", e)
    finally:
        client.close()

if __name__ == '__main__':
    check_evolution()
