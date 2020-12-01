# dist server

##Rules for Socket Communication 


In this Application there can be two types of socket connections:

    - controller
    - converter


There should always be only one instance of a converter connection.
This socket is in direct communication with python backend. It broadcasts
messages from the backend (like sensor-data & controll messages), to the
controller connections.

Controller connections receive data only from converter to display in 
frontend. Controller also sends back controll-messages which get only send 
to the converter

The socketserver has to know of which type a socketconnection is. The first
message should therefore be a JSON-Object containing the type.
For the beginning of the project there is a IP-Whitelist. Foreign connections
are going to be canceled immediatly.
To distinguish between ordinary JSON message and Authorization message, the server
is in need of a token. The token is constant and given.

TOKEN: '3b0e4add-1493-4cde-943c-6d47462f2a8b'

{
    auth: 'name'
    type: "converter/controller",
    token: $TOKEN,
}








'''
