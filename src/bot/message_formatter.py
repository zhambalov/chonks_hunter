def format_notification_message(token_id, price_eth, traits, rare_traits, collection_contract):
    rare_traits_list = [
        f"  • {trait['trait_type']}: {trait['value']}"
        for trait in traits
        if isinstance(trait, dict) and trait.get('trait_type') in rare_traits
    ]
    
    rare_traits_text = "\n".join(rare_traits_list)
    
    message = (
        f"🚨 <b>Rare Chonk Listed!</b> 🚨\n\n"
        f"<b>Chonk #{token_id}</b>\n"
        f"💰 Price: {price_eth:.3f} ETH\n\n"
        f"🎯 Rare Traits:\n{rare_traits_text}\n\n"
        f"🔗 <a href='https://opensea.io/assets/base/{collection_contract}/{token_id}'>View on OpenSea</a>"
    )
    return message