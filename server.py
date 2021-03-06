import asyncio
import websockets
import json
import yaml
import os
import sys

class SocketStates:
    FAILED = 'failed'
    SUCCESS = 'success'

class SocketServer:

    AUTH_TOKEN = '3b0e4add-1493-4cde-943c-6d47462f2a8b'
    C_TYPES = ['controller', 'converter']
    AUTH_MSG_KEYS = ['auth', 'type', 'token']

    def __init__(self, host, port, ip_whitelist=['0.0.0.0', '127.0.0.1']):
        self.HOST = host
        self.PORT = port
        self.IP_WHITELIST = ip_whitelist
        self.connections = []
        self.server = None

        # ---------- connections ------------ - - - >
        'e.g. { socket: <websocket-obj>, name: "name"  }'
        self.converter = {} 
        'e.g. [ { socket: <websocket-obj>, name: "name" }, { socket: <websocket-obj>, name: "name" }, ... ]'
        self.controllers = []
        # ---------- connections ------------ - - - >



    # -- improve this function
    # validate origin of connection
    def validate(self, websocket):
        if not websocket.remote_address[0] in self.IP_WHITELIST:
            return False
        else:
            return True

    # -- improve this function
    # check if connection is active and used
    def is_active(self, websocket):
        if websocket.closed == True:
            return False
        else:
            return True

    # check if websocket is authenticated
    def is_authenticated(self, websocket):
        # check if socket is already authenticated
        if self.converter.get('socket') == websocket:
            return True
        for obj in self.controllers:
            if obj.get('socket') == websocket:
                return True
        return False

    # expects dict
    def authenticate(self, msg):
        if msg.get('auth') == None:
            return False
        elif not msg.get('type') in self.C_TYPES:
            return False
        elif not msg.get('token') == self.AUTH_TOKEN:
            return False
        else:
            return True
    
    # check if message is authentication message
    def is_auth_msg(self, msg):
        try:
            msg = json.loads(msg)
            for key, value in msg.items():
                if not key in self.AUTH_MSG_KEYS:
                    return False
            else:
                return True
        except json.decoder.JSONDecodeError:
            return False 

    # delete entry in controllers or converter
    def delete_connection(self, websocket):
        if self.converter.get('socket') == websocket:
            self.converter = {}
            print("deleted converter")
            return
        for obj in self.controllers:
            if obj.get('socket') == websocket:
                self.controllers.remove(obj) 
                print("deleted controller")
                return
    
    # get the corresponding connection entry to given websocket-obj
    def get_connection_entry(self, websocket):
        if self.converter.get('socket') == websocket:
            return ("converter", self.converter)
        for obj in self.controllers:
            if obj.get('socket') == websocket:
                return ("controller", obj)
        return None

    async def write_to_connections(self, message, websocket):
        c_type = message.get('type')
        auth = message.get('auth')

        if c_type == 'converter':
            if self.converter.get('socket') != None:
                await websocket.send("converter already given. closing connection.")
                await websocket.close()
                self.delete_connection(websocket)
                print("{0} ----> converter already given. closing connection".format(websocket))
                return False
            else:
                print("converter added!")
                self.converter = { 'socket' : websocket, 'name' : auth }
                await websocket.send("success")
                return True

        elif c_type == 'controller':
            for obj in self.controllers:
                if obj.get('socket') == websocket:
                    await websocket.close()
                    self.delete_connection(websocket)
                    print("{0} ----> already authenticated".format(websocket))
                    return False
            self.controllers.append({ 'socket' : websocket, 'name' : auth })
            print("controller added")
            await websocket.send("success")
            return True

    # send a message to all connected controllers
    async def send_to_controllers(self, message):
        for obj in self.controllers:
            if self.is_active(obj.get('socket')):
                await obj.get('socket').send(message)

    # send a message to connected converter
    async def send_to_converter(self, message):
        # check if there is a converter
        if self.converter == {}:
            return 
        # if there is, send message to it
        else:
            if self.is_active(self.converter.get('socket')): 
                await self.converter.get('socket').send(message)
    
    # send a message to all conncetions
    async def send_to_all(self, message):
        await self.send_to_converter(message)
        await self.send_to_controllers(message)

    # send authentication state
    async def send_authentication_state(self, websocket, state):
        if self.is_active(websocket):
            auth_state = {
                    'type' : 'authentication_state', 
                    'state' : state } 
            await websocket.send(json.dumps(auth_state))

    # dispatch infos about all current connections to all endpoints
    async def dispatch_current_connections(self):
        currently_connected_message = { 
                'type' : 'currently_connected', 
                'converter' : str(self.converter),
                'controllers' : str(self.controllers) }
        await self.send_to_all(json.dumps(currently_connected_message))

    # ------- HANDLER --------
    async def handle(self, websocket, path):
        try:
            # reject connections of unknown IPs
            if not self.validate(websocket):
                await websocket.close()
                print("{0} ------> foreign address. closing connection.".format(websocket))
                return

            async for message in websocket:

                authenticated = False

                # check if socket is already authenticated if not:
                if not self.is_authenticated(websocket):
                    # check if message is authentication message
                    if self.is_auth_msg(message): 
                        msg = json.loads(message)
                        # try to authenticate
                        authenticated = self.authenticate(msg)
                        # write connection-obj on successfull authorization
                        if authenticated:
                            success = await self.write_to_connections(msg, websocket)
                            if not success:
                                return
                            print("{0} authenticated!".format(self.get_connection_entry(websocket)[1].get('name')))
                            await self.send_authentication_state(websocket, SocketStates.SUCCESS)
                            await self.dispatch_current_connections()
                            continue
                else:
                    authenticated = True
                                            
                # close connection if socket cannot be authenticated
                if not authenticated:
                    await websocket.close()
                    self.delete_connection(websocket)
                    print("{} ---> could not be authenticated. closing connection.".format(websocket))
                    return
                
                # defines what happens on regular message
                # get c_type
                c_type = self.get_connection_entry(websocket)[0]
                # if current websocket is converter 
                if c_type == 'converter':
                    # forward message to all controllers 
                    await self.send_to_controllers(message)
                # if current websocket is controller
                elif c_type == 'controller':
                    # forward message to converter 
                    await self.send_to_converter(message)
                elif c_type == None:
                    return
        
        # defines what happens if connection is closed. Either by peer or by Exception
        except websockets.exceptions.ConnectionClosedError:
            print("{0} ---> connection closed by peer".format(websocket))
        except Exception as e:
            print(e)
        finally:
            self.delete_connection(websocket)
            await self.dispatch_current_connections()
            print("{} ---> connection closed.".format(websocket))
            await websocket.close()
            return
        # ------------ HANDLER ENDS --------------

    def run(self):
        self.server = websockets.serve(self.handle, self.HOST, self.PORT)
        asyncio.get_event_loop().run_until_complete(self.server)
        try:
            print("starting server at {0}:{1}".format(self.HOST, self.PORT))
            asyncio.get_event_loop().run_forever()
        except Exception as e:
            print(e)


if __name__ == "__main__":

    config = None

    if os.path.isfile('./conf.yaml'):
        with open('./conf.yaml', 'r') as conf:
            config = yaml.load(conf, Loader=yaml.FullLoader)
    else:
        print("no configuration file \n")
        sys.exit()

    host = config.get('host')
    port = config.get('port')
    ip_whitelist = config.get('ip_whitelist')

    s = SocketServer(host, port, ip_whitelist=ip_whitelist)
    try:
        s.run()
    except KeyboardInterrupt:
        print("exit")

