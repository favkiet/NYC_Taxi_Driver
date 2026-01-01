# NYC Taxi Demand Prediction

This project aims to predict taxi demand in New York City based on historical trip data. It includes data processing, exploratory analysis, and a web API to serve predictions.

## Project Structure

```
.
├── data/
│   ├── processed/
│   └── raw/
│       └── 2025/
├── notebooks/
│   └── exploratory_data_analysis.ipynb
├── scripts/
│   ├── data_processing.py
│   ├── explore_data.py
│   └── train_model.py
├── src/
│   ├── api/
│   │   └── main.py
│   ├── data_processing/
│   │   └── main.py
│   └── modeling/
│       └── main.py
├── requirements.txt
└── README.md
```

- **`data/`**: Contains raw and processed taxi trip data.
- **`notebooks/`**: Jupyter notebook for exploratory data analysis.
- **`scripts/`**: Standalone scripts for different tasks like data processing and model training.
- **`src/`**: Source code for the main application, including the API.
- **`requirements.txt`**: A list of Python dependencies for this project.

## Getting Started

### Prerequisites

- Python 3.8+
- An environment with the dependencies installed.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/NYC_Driver.git
    cd NYC_Driver
    ```

2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Data Processing

The `scripts/data_processing.py` script processes the raw parquet files from `data/raw/2025/` and saves the result in `data/processed/`.

To run the script:
```bash
python scripts/data_processing.py
```

### Exploratory Analysis

The `notebooks/exploratory_data_analysis.ipynb` notebook contains an analysis of the taxi trip data. To run it, you need to have a Jupyter environment.

### Model Training

The `scripts/train_model.py` script is a placeholder for the model training logic. This part of the project is not yet implemented.

### Running the API

The project includes a FastAPI application to serve the demand predictions.

**Note:** The API tries to load a pre-trained XGBoost model from `../modeling/xgboost_model.json`, which is not included in this repository. You need to train a model first and save it to the specified path.

To run the API server:
```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

#### API Endpoints

- **`GET /`**: Returns a welcome message.
- **`GET /predict`**: Predicts taxi demand.
  - **Query Parameters:**
    - `zone`: The taxi zone ID (PULocationID).
    - `month`: The month of the year (1-12).
    - `day_of_week`: The day of the week (0=Monday, 6=Sunday).
    - `hour`: The hour of the day (0-23).
  - **Example:**
    ```
    http://127.0.0.1:8000/predict?zone=42&month=10&day_of_week=3&hour=18
    ```