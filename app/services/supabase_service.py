"""
This file defines the SupabaseService class, which is a concrete implementation
of the BaseDatabaseService interface for interacting with a Supabase database.

It provides methods for performing common database operations such as updating,
inserting, upserting, deleting, and selecting data, leveraging the official
Supabase Python client library. The service uses environment variables for
Supabase URL and service role key for authentication.
"""

from app.services.base_database_service import BaseDatabaseService
from app.core.config import settings
from supabase import create_client
from typing import Dict, Any, Union, List
import logging

logger = logging.getLogger(__name__)


class SupbaseException(Exception):
    pass


class SupabaseService(BaseDatabaseService):
    """
    An implementation of BaseDatabaseService for interacting with a Supabase database.

    This class provides methods for performing common database operations such as
    updating, inserting, upserting, deleting, and selecting data within a Supabase project.
    It utilizes the official Supabase Python client library.
    """

    def __init__(self):
        """
        Initializes the SupabaseService with the Supabase URL and service role key
        from the application settings, and creates a Supabase client instance.
        """
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.supabase_client = create_client(self.base_url, self.api_key)

    def update_data(
        self, table_name: str, data: Dict, **kwargs
    ) -> Dict[str, Any]:
        """
        Updates records in the specified Supabase table that match the given criteria.

        Args:
            table_name (str): The name of the Supabase table to update.
            data (Dict): A dictionary containing the column names and their new values.
            **kwargs: Additional keyword arguments. Must include 'cols' which is a
                      dictionary of column names and values to filter the update.

        Returns:
            Dict[str, Any]: The response from the Supabase update operation.

        Raises:
            SupbaseException: If an error occurs during the Supabase update operation.
        """
        try:
            logger.info(f"Updating table {table_name} with data: {data}")
            # dict of column names and values to filter
            cols = kwargs["cols"]
            response = (
                self.supabase_client.table(table_name)
                .update(data)
                .match(cols)
                .execute()
                .model_dump()
            )
            return response
        except Exception as e:
            logger.error(f"Failed to update table {table_name} with error: {str(e)}")
            raise SupbaseException(
                f"An error occured while updating table: {table_name}"
            )

    def insert_data(
        self, table_name: str, data: Dict, **kwargs
    ) -> Dict[str, Any]:
        """
        Inserts a new record into the specified Supabase table.

        Args:
            table_name (str): The name of the Supabase table to insert into.
            data (Dict): A dictionary containing the column names and their values for the new record.
            **kwargs: Additional keyword arguments (currently not used in this implementation).

        Returns:
            Dict[str, Any]: The response from the Supabase insert operation.

        Raises:
            SupbaseException: If an error occurs during the Supabase insert operation.
        """
        try:
            logger.info(f"Inserting into table {table_name} with data: {data}")
            response = (
                self.supabase_client.table(table_name)
                .insert(data)
                .execute()
                .model_dump()
            )
            return response
        except Exception as e:
            logger.error(
                f"Failed to insert data into table {table_name} with error: {str(e)}"
            )
            raise SupbaseException(
                f"An error occured while inserting into table: {table_name}"
            )

    def upsert_data(
        self, table_name: str, data: Dict, **kwargs
    ) -> Dict[str, Any]:
        """
        Inserts a new record or updates an existing record in the specified Supabase table.

        If a record with the same primary key (or other defined unique constraint) exists,
        it will be updated with the provided data; otherwise, a new record will be inserted.

        Args:
            table_name (str): The name of the Supabase table to upsert into.
            data (Dict): A dictionary containing the column names and their values.
            **kwargs: Additional keyword arguments (currently not used in this implementation).

        Returns:
            Dict[str, Any]: The response from the Supabase upsert operation.

        Raises:
            SupbaseException: If an error occurs during the Supabase upsert operation.
        """
        try:
            logger.info(f"Upserting table {table_name} with data: {data}")
            response = (
                self.supabase_client.table(table_name)
                .upsert(data)
                .execute()
                .model_dump()
            )
            return response
        except Exception as e:
            logger.error(f"Failed to upsert table {table_name} with error: {str(e)}")
            raise SupbaseException(
                f"An error occured while upserting table: {table_name}"
            )

    def delete_data(self, table_name: str, **kwargs) -> Dict[str, Any]:
        """
        Deletes records from the specified Supabase table that match the given criteria.

        Args:
            table_name (str): The name of the Supabase table to delete from.
            **kwargs: Additional keyword arguments. Must include 'cols' which is a
                      dictionary of column names and values to filter the deletion.

        Returns:
            Dict[str, Any]: The response from the Supabase delete operation.

        Raises:
            SupbaseException: If an error occurs during the Supabase delete operation.
        """
        try:
            logger.info(f"Deleting data from table {table_name}")
            cols = kwargs["cols"]
            response = (
                self.supabase_client.table(table_name)
                .delete()
                .match(cols)
                .execute()
                .model_dump()
            )
            return response
        except Exception as e:
            logger.error(
                f"Failed to delete data from {table_name} with error: {str(e)}"
            )
            raise SupbaseException(
                f"An error occured while deleting data from table: {table_name}"
            )

    def select_data(self, table_name, **kwargs) -> Union[List[Any], str]:
        """
        Fetches records from the specified Supabase table based on the provided criteria.

        Args:
            table_name (str): The name of the Supabase table to select from.
            **kwargs: Additional keyword arguments.
                - 'query' (Optional[str]): The columns to select (defaults to '*').
                - 'cols' (Dict): A dictionary of column names and values to filter the selection using exact matching.

        Returns:
            Dict[str, Any]: The response from the Supabase select operation.

        Raises:
            SupbaseException: If an error occurs during the Supabase select operation.
        """

        try:
            logger.info(f"Fetching data from table {table_name}")
            query = kwargs.get("query", "*")
            cols = kwargs.get("cols", None)
            if cols:
                response = (
                    self.supabase_client.table(table_name)
                    .select(query)
                    .match(cols)
                    .execute()
                    .model_dump()
                )
            else:
                response = (
                    self.supabase_client.table(table_name)
                    .select(query)
                    .execute()
                    .model_dump()
                )
            return response.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch data from {table_name} with error: {str(e)}")
            raise SupbaseException(
                f"An error occured while fetching data from table: {table_name}"
            )
        
    def rpc(self, function_name: str, params: Dict = None, **kwargs) -> Union[List[Any], Dict[str, Any]]:
        """
        Calls a stored PostgreSQL function via Supabase's RPC endpoint.

        Args:
            function_name (str): The name of the PostgreSQL function to call
            params (Dict, optional): Parameters to pass to the function
            **kwargs: Additional keyword arguments for future extensions

        Returns:
            Union[List[Any], Dict[str, Any]]: The response from the function call

        Raises:
            SupbaseException: If an error occurs during the RPC call
        """
        try:
            logger.info(f"Calling RPC function {function_name} with params: {params}")
            
            # Call the function with parameters if provided
            if params:
                response = self.supabase_client.rpc(function_name, params).execute().model_dump()
            else:
                response = self.supabase_client.rpc(function_name).execute().model_dump()
            
            return response.get("data", [])
        
        except Exception as e:
            error_msg = f"Failed to execute RPC function {function_name} with error: {str(e)}"
            logger.error(error_msg)
            raise SupbaseException(error_msg)
