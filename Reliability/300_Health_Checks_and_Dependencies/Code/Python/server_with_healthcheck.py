# This is a simple test server for use with the Well-Architected labs
# It simulates an engine for recommending TV shows

from http.server import BaseHTTPRequestHandler, HTTPServer
from functools import partial
from ec2_metadata import ec2_metadata
import sys
import getopt
import boto3
import traceback
import random

# html code for the default page served by this server
html = """
<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <title>Resiliency Workshop</title>
    </head>
    <body>
        <h1>Enjoy some classic television</h1>
        <p>{Message}</p>
        <p>{Content}</p>
        <p><a href="{Link}"><br/><br/>click here to make a healthcheck request</a></p>
    </body>
</html>"""

# RequestHandler: Response depends on type of request made
class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, client, *args, **kwargs):
        self.client = client
        super().__init__(*args, **kwargs)

    def do_GET(self):
        print("path: ", self.path)

        # Default request URL without additional path info)
        if self.path == '/':
            link = "healthcheck"
            try:
                message_parts = [
                    'account_id: %s' % ec2_metadata.account_id,
                    'ami_id: %s' % ec2_metadata.ami_id,
                    'availability_zone: %s' % ec2_metadata.availability_zone,
                    'instance_id: %s' % ec2_metadata.instance_id,
                    'instance_type: %s' % ec2_metadata.instance_type,
                    'private_hostname: %s' % ec2_metadata.private_hostname,
                    'private_ipv4: %s' % ec2_metadata.private_ipv4
                ]
                message = '<br>'.join(message_parts)
            except Exception:
                message = "Running outside AWS"

            message += "<h1>What to watch next....</h1>"
            # Call our service dependency
            # This currently uses a randomly generated user.
            # In the future maybe allow student to supply the user ID as input

            # Generate User ID between 1 and 4
            userId = str(random.randint(1, 4))

            # Call the recommendation service 
            # (actually just a simply lookup in a DynamoDB table, which is acting as a mock for the recommendation service)
            try:
                response = self.client.get_item(
                    TableName="serviceCallMocks",
                    Key={
                        'ServiceAPI': {
                            'S': 'getRecommendation',
                        },
                        'UserID': {
                            'N': userId,
                        }
                    }
                )

                # Parses value of recommendation from DynamoDB JSON return value
                # {'Item': {
                #     'ServiceAPI': {'S': 'getRecommendation'}, 
                #     'UserID': {'N': '1'}, 
                #     'Result': {'S': 'M*A*S*H'},  ...
                tv_show = response['Item']['Result']['S']
                user_name = response['Item']['UserName']['S']
                message += '<br>' + recommendation_message (user_name, tv_show, True)

            # If our dependency fails, and we cannot make a personalized recommendation
            # then give a pre-selected (static) recommendation
            except Exception as e:
                message += recommendation_message ('Valued Customer', 'I Love Lucy', False)
                message += '<br><br><br><h2>Diagnostic Info:</h2>'
                message += '<br>We are unable to provide personalized recommendations'
                message += '<br>If this persists, please report the following info to us:'
                message += str(traceback.format_exception_only(e.__class__, e))

            # Send response status code
            self.send_response(200)

            # Send headers
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(
                bytes(
                    html.format(Content=message, Message="Data from the metadata API", Link=link),
                    "utf-8"
                )
            )

        # Healthcheck request
        elif self.path == '/healthcheck':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>healthcheck</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>success</body></html>", "utf-8"))

            # @TODO Add check for service dependency - if not available return 503 Service Unavailable.

        return

# Utility function to consistently format how recommendations are displayed
def recommendation_message (user_name, tv_show, is_custom_recco):
    if is_custom_recco:
        tag_line = "your recommendation is"
    else:
        tag_line = "everyone enjoys this classic"
    cell1 = "<b>" + user_name + "</b>, " + tag_line + ":"
    cell2 = "<b>" + tv_show + "</b>"
    recco_msg = "<table border=\"5\"><tr>" + "<td>" + cell1 + "</td>" + "<td>" + cell2 + "</td>" + "</tr></table>"
    return recco_msg

# Initialize server
def run(argv):
    try:
        opts, args = getopt.getopt(
            argv,
            "h:p:r:",
            [
                "help"
                "server_port=",
                "region="
            ]
        )
    except getopt.GetoptError:
        print('server.py -p <server_port> -r <AWS region>')
        sys.exit(2)
    print(opts)

    # Default value - will be over-written if supplied via args
    server_port = 80
    try:
        region = ec2_metadata.region
    except:
        region = 'us-east-2'

    for opt, arg in opts:
        if opt == '-h':
            print('test.py -p <server_port> ')
            sys.exit()
        elif opt in ("-p", "--server_port"):
            server_port = int(arg)
        elif opt in ("-r", "--region"):
            region = arg

    # Setup client for DDB -- we will use this to mock a service dependency
    client = boto3.client('dynamodb', region)

    print('starting server...')
    server_address = ('0.0.0.0', server_port)

    handler = partial(RequestHandler, client)
    httpd = HTTPServer(server_address, handler)
    print('running server...')
    httpd.serve_forever()


if __name__ == "__main__":
    run(sys.argv[1:])