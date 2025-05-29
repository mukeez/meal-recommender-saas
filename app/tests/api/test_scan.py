import pytest
from app.core.config import settings
from app.tests.constants.scan import ScanTestConstants
from io import BytesIO
import httpx
import json


@pytest.mark.asyncio
class TestScanEndpoint:
    async def test_scan_barcode_product_from_db_success(
        self,
        authenticated_client,
        mock_product_scan_barcode,
        mock_logged_products_model,
    ):
        """Integration test for successful retrieval of product from db after barcode scan."""
        mock_product_scan_barcode.return_value = [mock_logged_products_model]

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/scan/barcode",
            json={"barcode": ScanTestConstants.BARCODE.value},
        )

        assert response.status_code == 200

        assert response.json() == ScanTestConstants.SCAN_DATA.value

        mock_product_scan_barcode.assert_called_once_with(
            barcode=ScanTestConstants.BARCODE.value
        )

    async def test_scan_invalid_barcode(
        self, authenticated_client, mock_product_scan_barcode
    ):
        """Integration test for response for invalid barcode ie barcode is not a digit"""

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/scan/barcode", json={"barcode": "testbarcode"}
        )

        assert response.status_code == 400

        assert response.json() == {
            "detail": "Invalid barcode format. Barcode must contain only digits."
        }

        mock_product_scan_barcode.assert_not_called()

    async def test_scan_barcode_openfoodfacts_success(
        self,
        authenticated_client,
        mock_product_scan_barcode,
        mock_openfoodfacts_scan_barcode,
        mock_product_log_product,
        mock_logged_products_model,
    ):
        """Integration test for successful retrieval of product from openfoodfacts after barcode scan."""

        mock_product_scan_barcode.return_value = None

        mock_openfoodfacts_scan_barcode.return_value = mock_logged_products_model

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/scan/barcode",
            json={"barcode": ScanTestConstants.BARCODE.value},
        )

        assert response.status_code == 200

        assert response.json() == ScanTestConstants.SCAN_DATA.value

        mock_product_scan_barcode.assert_called_once_with(
            barcode=ScanTestConstants.BARCODE.value
        )

        # assert product_service.log_product called
        mock_product_log_product.assert_called_once()

        # assert openfoodfact_service.scan_barcode called
        mock_openfoodfacts_scan_barcode.assert_called_once_with(
            barcode=ScanTestConstants.BARCODE.value
        )

    async def test_scan_image_success(
        self, authenticated_client, mock_scan_encoded_image, mock_scan_image_ai
    ):
        """Integration test for successful scanning of images by vision API."""

        mock_scan_encoded_image.decode.return_value = "SGVsbG8sIHdvcmxkIQ=="

        mock_scan_image_ai.return_value = httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(ScanTestConstants.SCAN_DATA.value)
                        }
                    }
                ]
            },
        )

        file_content = b"fake image data"
        files = {"image": ("breakfast.png", BytesIO(file_content), "image/png")}

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/scan/image", files=files
        )

        assert response.status_code == 200

        assert response.json() == ScanTestConstants.SCAN_DATA.value

        # assert vision api called
        mock_scan_image_ai.assert_called_once()
