import os

from deployer.server import app


if __name__ == '__main__':
    app.run(debug=True,
            host='0.0.0.0',
            port=int(os.getenv('API_PORT', '9000')))
