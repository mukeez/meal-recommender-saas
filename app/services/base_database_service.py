from typing import List, Type, Any, Optional, Union


class BaseDatabaseService:
    """
    Base class for database service implementations.

    This class defines the interface for common database operations
    such as updating, inserting, deleting, and selecting data. Concrete
    database service implementations should inherit from this class and
    override the abstract methods to provide specific database interactions.

    The class also maintains a registry of its subclasses to allow for
    dynamic discovery of available database service implementations.
    """

    # class‐level list of all concrete subclasses
    subclasses: List[Type["BaseDatabaseService"]] = []

    def __init_subclass__(cls, **kwargs):
        """
        Metaclass hook that registers concrete subclasses of BaseDatabaseService.

        This ensures that all specific database service implementations are
        tracked in the `subclasses` list.
        """
        super().__init_subclass__(**kwargs)
        # skip the base class itself
        if cls is not BaseDatabaseService:
            BaseDatabaseService.subclasses.append(cls)

    def update_data(self, table_name: str, data: Optional[Any], **kwargs) -> Any:
        """
        Updates a record in the specified table.

        This is a default stub method that must be overridden by concrete
        subclasses to provide the actual database update logic.

        Args:
            table_name (str): The name of the table to update.
            data (Optional[Any]): The data to update the record with.
            **kwargs: Additional keyword arguments that might be specific
                      to the underlying database implementation.

        Raises:
            NotImplementedError: If this method is called directly from the
                                 BaseDatabaseService class.
        """
        cls_name = type(self).__name__
        raise NotImplementedError(f"{cls_name}.update_data not implemented")

    def insert_data(self, table_name: str, data: Any, **kwargs) -> Any:
        """
        Inserts a new record into the specified table.

        This is a default stub method that must be overridden by concrete
        subclasses to provide the actual database insertion logic.

        Args:
            table_name (str): The name of the table to insert into.
            data (Any): The data for the new record.
            **kwargs: Additional keyword arguments that might be specific
                      to the underlying database implementation.

        Raises:
            NotImplementedError: If this method is called directly from the
                                 BaseDatabaseService class.
        """
        cls_name = type(self).__name__
        raise NotImplementedError(f"{cls_name}.insert_data not implemented")

    def delete_data(self, table_name: str) -> Any:
        """
        Deletes one or more records from the specified table.

        This is a default stub method that must be overridden by concrete
        subclasses to provide the actual database deletion logic.

        Args:
            table_name (str): The name of the table to delete from.
            **kwargs: Additional keyword arguments that might be specific
                      to the underlying database implementation.

        Raises:
            NotImplementedError: If this method is called directly from the
                                 BaseDatabaseService class.
        """
        cls_name = type(self).__name__
        raise NotImplementedError(f"{cls_name}.delete_data not implemented")

    def select_data(self, table_name: str, **kwargs) -> Any:
        """
        Selects records from the specified table based on provided criteria.

        This is a default stub method that must be overridden by concrete
        subclasses to provide the actual database selection logic.

        Args:
            table_name (str): The name of the table to select from.
            **kwargs: Keyword arguments specifying the selection criteria
                      (e.g., conditions, filters, joins), which will be
                      specific to the underlying database implementation.

        Raises:
            NotImplementedError: If this method is called directly from the
                                 BaseDatabaseService class.
        """
        cls_name = type(self).__name__
        raise NotImplementedError(f"{cls_name}.select_data not implemented")

    def rpc(self, function_name: str, params: Optional[dict] = None, **kwargs) -> Any:
        """
        Calls a stored procedure or function in the database.

        This is a default stub method that must be overridden by concrete
        subclasses to provide the actual RPC logic.

        Args:
            function_name (str): The name of the stored procedure or function to call.
            params (Optional[dict]): Parameters to pass to the function.
            **kwargs: Additional keyword arguments that might be specific
                      to the underlying database implementation.

        Returns:
            Any: The result of the RPC call.

        Raises:
            NotImplementedError: If this method is called directly from the
                                 BaseDatabaseService class.
        """
        cls_name = type(self).__name__
        raise NotImplementedError(f"{cls_name}.rpc not implemented")
