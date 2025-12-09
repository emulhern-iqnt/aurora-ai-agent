class SQLErrorHandler:
    """
    A class to track SQL errors during the runtime of the main client.
    It maintains a list of errors that can be logged, retrieved, or cleared.
    """

    def __init__(self):
        """Initialize the error handler with an empty list."""
        self.errors = []

    def log_error(self, error_message: str):
        """
        Log an SQL error by appending it to the list.

        :param error_message: The error message or details to log.
        """
        self.errors.append(error_message)

    def get_errors(self) -> list:
        """
        Retrieve the list of all logged SQL errors.

        :return: A list of error messages.
        """
        return self.errors.copy()  # Return a copy to prevent external modification

    def clear_errors(self):
        """Clear the list of logged errors."""
        self.errors = []

# Example usage (for testing purposes; remove if not needed)
if __name__ == "__main__":
    handler = SQLErrorHandling()
    handler.log_error("SQL Error: Connection timed out")
    handler.log_error("SQL Error: Invalid query syntax")
    print(handler.get_errors())  # Output: ['SQL Error: Connection timed out', 'SQL Error: Invalid query syntax']
    handler.clear_errors()
    print(handler.get_errors())  # Output: []