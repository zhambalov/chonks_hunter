from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class NFTTrait:
    trait_type: str
    value: str

@dataclass
class NFTMetadata:
    token_id: str
    traits: List[NFTTrait]
    
    @classmethod
    def from_response(cls, data: Dict) -> 'NFTMetadata':
        """Create NFTMetadata from OpenSea API response"""
        traits = [
            NFTTrait(
                trait_type=trait.get('trait_type', ''),
                value=trait.get('value', '')
            )
            for trait in data.get('traits', [])
            if isinstance(trait, dict)
        ]
        
        return cls(
            token_id=data.get('token_id', ''),
            traits=traits
        )

@dataclass
class ListingData:
    token_id: str
    price_wei: str
    nft_id: str
    
    @classmethod
    def from_payload(cls, payload: Dict) -> Optional['ListingData']:
        """Create ListingData from websocket payload"""
        try:
            item_data = (payload.get('payload', {}) or payload).get('item', {})
            if not item_data:
                return None
                
            nft_id = item_data.get('nft_id')
            if not nft_id:
                return None
                
            return cls(
                nft_id=nft_id,
                token_id=nft_id.split('/')[-1],
                price_wei=payload.get('base_price', 
                    payload.get('payload', {}).get('base_price', '0'))
            )
        except Exception:
            return None