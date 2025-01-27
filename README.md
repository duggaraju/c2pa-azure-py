# c2pa-azure-py

A Python project to use the c2pa Python library and Azure code signing service to add content credentials to a file.

## Installation

1. Clone the repository:

    ```sh
    git clone https://github.com/duggaraju/c2pa-azure-py.git
    cd c2pa-azure-py
    ```

2. Create a virtual environment and activate it:

    ```sh
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required dependencies:

    ```sh
    pip install -r requirements.txt
    ```
4. Tempoary workaround for bug in c2pa-pyton package. (Can be ignored once c2pa-python package 0.62.0 or above is released)
```sh
git clone https://github.com/contentauth/c2pa-pyton ../
python3 -m pip install ../c2pa-python
```
## Usage

1. Configure your Azure code signing credentials in `config.json`.

2. Run the script to add content credentials to your file:

    ```sh
    python src/main.py -i <input> -o <output> -e <signing endpoint> -a <account> -c <certificate profile>
    ```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
