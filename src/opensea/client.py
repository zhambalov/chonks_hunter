import logging
import aiohttp

class OpenSeaClient:
    def __init__(self, api_key, api_url, api_limiter):
        self.api_key = api_key
        self.api_url = api_url
        self.api_limiter = api_limiter
        self.headers = {
            "accept": "application/json",
            "x-api-key": self.api_key
        }

    async def get_nft_metadata(self, chain, contract, token_id):
        await self.api_limiter.acquire()
        try:
            url = f"{self.api_url}/chain/{chain}/contract/{contract}/nfts/{token_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('nft', {})
                    else:
                        logging.error(f"Failed to fetch metadata: {response.status}")
                        return None
        except Exception as e:
            logging.error(f"Error fetching metadata from API: {e}")
            return None

    def format_price(self, price_data):
        try:
            if not price_data:
                return 0.0
            price_wei = float(str(price_data))
            return price_wei / (10 ** 18)
        except (ValueError, TypeError) as e:
            logging.error(f"Error converting price {price_data}: {e}")
            return 0.0