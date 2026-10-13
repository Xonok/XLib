#!/usr/bin/env python3
"""
Selenium tests for the WebSocket example server.

These tests verify that the WebSocket implementation works correctly
with a real browser (Chrome/Firefox via Selenium).

Run with: python3 test_selenium.py

Requires:
- selenium (pip install selenium)
- ChromeDriver or GeckoDriver in PATH
"""

import os,sys,time,threading,subprocess,signal

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(os.path.dirname(HERE))
if DEV_DIR not in sys.path:
	sys.path.insert(0, DEV_DIR)

def start_server():
	"""Start the example server in a subprocess."""
	server_script = os.path.join(HERE, 'example_server.py')
	proc = subprocess.Popen(
		[sys.executable, server_script],
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
	)
	# Wait for server to start
	time.sleep(2)
	return proc

def stop_server(proc):
	"""Stop the server subprocess."""
	proc.terminate()
	try:
		proc.wait(timeout=5)
	except subprocess.TimeoutExpired:
		proc.kill()
		proc.wait()

def test_with_chrome():
	"""Run tests with Chrome."""
	from selenium import webdriver
	from selenium.webdriver.chrome.options import Options
	from selenium.webdriver.common.by import By
	from selenium.webdriver.support.ui import WebDriverWait
	from selenium.webdriver.support import expected_conditions as EC
	from selenium.common.exceptions import TimeoutException, WebDriverException
	
	chrome_options = Options()
	chrome_options.add_argument('--headless')
	chrome_options.add_argument('--no-sandbox')
	chrome_options.add_argument('--disable-dev-shm-usage')
	chrome_options.add_argument('--disable-gpu')
	
	driver = None
	try:
		driver = webdriver.Chrome(options=chrome_options)
		driver.set_page_load_timeout(30)
		
		# Navigate to the test page
		driver.get('http://127.0.0.1:8080/')
		
		wait = WebDriverWait(driver, 10)
		
		# Wait for connection status to become "Connected"
		status_elem = wait.until(
			EC.text_to_be_present_in_element((By.ID, 'status'), 'Connected')
		)
		
		# Verify status shows connected
		status_text = driver.find_element(By.ID, 'status').text
		assert 'Connected' in status_text, f"Expected 'Connected', got '{status_text}'"
		print("✓ WebSocket connected successfully")
		
		# Find message input and send button
		message_input = driver.find_element(By.ID, 'messageInput')
		send_btn = driver.find_element(By.ID, 'sendBtn')
		
		# Send a test message
		test_message = "Hello from Selenium!"
		message_input.send_keys(test_message)
		send_btn.click()
		
		# Wait for echo message to appear in messages
		messages_div = driver.find_element(By.ID, 'messages')
		
		# Wait for the message to appear (both sent and received)
		wait.until(
			lambda d: test_message in d.find_element(By.ID, 'messages').text
		)
		
		# Verify echo received
		messages_text = messages_div.text
		assert test_message in messages_text, f"Sent message not found in messages"
		assert f"Echo: {test_message}" in messages_text, f"Echo not received"
		print("✓ Message sent and echo received")
		
		# Send another message
		test_message2 = "Second test message"
		message_input.clear()
		message_input.send_keys(test_message2)
		send_btn.click()
		
		wait.until(
			lambda d: test_message2 in d.find_element(By.ID, 'messages').text
		)
		
		messages_text = messages_div.text
		assert test_message2 in messages_text
		assert f"Echo: {test_message2}" in messages_text
		print("✓ Second message sent and echo received")
		
		# Test disconnect
		disconnect_btn = driver.find_element(By.ID, 'disconnectBtn')
		disconnect_btn.click()
		
		# Wait for disconnected status
		wait.until(
			EC.text_to_be_present_in_element((By.ID, 'status'), 'Disconnected')
		)
		
		status_text = driver.find_element(By.ID, 'status').text
		assert 'Disconnected' in status_text
		print("✓ Disconnect works correctly")
		
		# Reconnect
		connect_btn = driver.find_element(By.ID, 'connectBtn')
		connect_btn.click()
		
		wait.until(
			EC.text_to_be_present_in_element((By.ID, 'status'), 'Connected')
		)
		
		status_text = driver.find_element(By.ID, 'status').text
		assert 'Connected' in status_text
		print("✓ Reconnect works correctly")
		
		return True
		
	except TimeoutException as e:
		print(f"✗ Timeout: {e}")
		if driver:
			print(f"Page source: {driver.page_source[:2000]}")
		return False
	except WebDriverException as e:
		print(f"✗ WebDriver error: {e}")
		return False
	except AssertionError as e:
		print(f"✗ Assertion failed: {e}")
		if driver:
			print(f"Page source: {driver.page_source[:2000]}")
		return False
	finally:
		if driver:
			driver.quit()

def test_with_firefox():
	"""Run tests with Firefox."""
	from selenium import webdriver
	from selenium.webdriver.firefox.options import Options
	from selenium.webdriver.common.by import By
	from selenium.webdriver.support.ui import WebDriverWait
	from selenium.webdriver.support import expected_conditions as EC
	from selenium.common.exceptions import TimeoutException, WebDriverException
	
	firefox_options = Options()
	firefox_options.add_argument('--headless')
	
	driver = None
	try:
		driver = webdriver.Firefox(options=firefox_options)
		driver.set_page_load_timeout(30)
		
		driver.get('http://127.0.0.1:8080/')
		
		wait = WebDriverWait(driver, 10)
		
		# Wait for connection
		wait.until(
			EC.text_to_be_present_in_element((By.ID, 'status'), 'Connected')
		)
		
		status_text = driver.find_element(By.ID, 'status').text
		assert 'Connected' in status_text
		print("✓ WebSocket connected (Firefox)")
		
		message_input = driver.find_element(By.ID, 'messageInput')
		send_btn = driver.find_element(By.ID, 'sendBtn')
		
		test_message = "Hello from Firefox!"
		message_input.send_keys(test_message)
		send_btn.click()
		
		wait.until(
			lambda d: test_message in d.find_element(By.ID, 'messages').text
		)
		
		messages_text = driver.find_element(By.ID, 'messages').text
		assert test_message in messages_text
		assert f"Echo: {test_message}" in messages_text
		print("✓ Message sent and echo received (Firefox)")
		
		return True
		
	except TimeoutException as e:
		print(f"✗ Timeout (Firefox): {e}")
		return False
	except WebDriverException as e:
		print(f"✗ WebDriver error (Firefox): {e}")
		return False
	except AssertionError as e:
		print(f"✗ Assertion failed (Firefox): {e}")
		return False
	finally:
		if driver:
			driver.quit()

def main():
	"""Main test runner."""
	print("Starting WebSocket server...")
	server_proc = start_server()
	
	try:
		# Give server time to fully start
		time.sleep(3)
		
		# Check if server is running
		try:
			import urllib.request
			response = urllib.request.urlopen('http://127.0.0.1:8080/', timeout=5)
			print(f"Server responding: {response.status}")
		except Exception as e:
			print(f"Server not responding: {e}")
			stdout, stderr = server_proc.communicate(timeout=2)
			print(f"Server stdout: {stdout.decode()}")
			print(f"Server stderr: {stderr.decode()}")
			return 1
		
		print("\n=== Running Selenium Tests ===\n")
		
		# Try Chrome first
		print("Testing with Chrome...")
		chrome_result = test_with_chrome()
		
		print()
		
		# Try Firefox
		print("Testing with Firefox...")
		firefox_result = test_with_firefox()
		
		print("\n=== Results ===")
		print(f"Chrome:  {'PASS' if chrome_result else 'FAIL'}")
		print(f"Firefox: {'PASS' if firefox_result else 'FAIL'}")
		
		if chrome_result or firefox_result:
			print("\n✓ At least one browser test passed!")
			return 0
		else:
			print("\n✗ All browser tests failed!")
			return 1
			
	finally:
		print("\nStopping server...")
		stop_server(server_proc)

if __name__ == '__main__':
	sys.exit(main())
