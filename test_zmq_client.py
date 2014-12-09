#
# Request-reply client in Python
# Connects REQ socket to tcp://localhost:5559
# Sends "Hello" to server, expects "World" back
#
import zmq

# Prepare our context and sockets
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect('ipc:///tmp/python-elude')
print('connected')

# Do 10 requests, waiting each time for a response
socket.send('http://finance.google.com'.encode('utf8'))
message = socket.recv()
print("Received reply [%s]" % message)
'''
for request in range(1, 100):
    socket.send(("Hello %d" % request).encode('utf8'))
    message = socket.recv()
    print("Received reply %s [%s]" % (request, message))
'''