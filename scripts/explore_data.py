from pyspark.sql import SparkSession

# Define the path to the data file
file_path = "data/raw/2025/yellow_tripdata_2025-01.parquet"

def read_and_explore_data_spark(file_path: str) -> None:
    """
    Reads a parquet file with Spark and prints the first 5 rows of the resulting dataframe.
    """
    print(f"Reading data from {file_path}")

    # Create or get SparkSession
    spark = (
        SparkSession.builder
        .appName("ReadAndExploreTaxiTrips")
        .getOrCreate()
    )

    # Read the parquet file into a Spark DataFrame
    df = spark.read.parquet(file_path)

    # Print schema (useful for exploration)
    print("Schema of the data:")
    df.printSchema()

    # Show the first 5 rows
    print("First 5 rows of the data:")
    df.show(5, truncate=False)

    # Stop SparkSession (good practice for scripts)
    spark.stop()

if __name__ == "__main__":
    read_and_explore_data_spark(file_path)
