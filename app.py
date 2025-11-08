from flask import Flask, request, render_template, jsonify
import json

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # data = request.get_json()  # returns a Python dict
        # if not data:
        #     return jsonify({'error': 'No JSON received'}), 400
        # Get all values of inputs named 'input_field'
        inputs = request.form.getlist('input_field')
        # Now inputs is a Python list of strings
        print(inputs)  # For debugging in console

        data = read_json()
        print(data)

        return f"You submitted: {inputs}"
    return render_template('index.html')

# @app.route('/read-json')
def read_json():
    try:
        # Open and read the JSON file
        with open('data.json', 'r') as f:
            data = json.load(f)  # loads JSON into a Python dict
    except FileNotFoundError:
        return jsonify({'error': 'JSON file not found'}), 404
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON file'}), 400

    # Now `data` is a Python dictionary
    print("Loaded data:", data)

    # You can manipulate it or just return it as JSON
    return jsonify(data)


if __name__ == '__main__':
    app.run(debug=True)
