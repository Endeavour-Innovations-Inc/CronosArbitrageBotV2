import json
import requests
from web3 import Web3
from decimal import Decimal

def load_contract_abi(file_name):
    with open(file_name, 'r') as f:
        return json.load(f)

def fetch_token_price_from_coingecko(contract_address):
    platform_id = 'cronos'
    contract_address_lower = contract_address.lower()
    url = f"https://api.coingecko.com/api/v3/simple/token_price/{platform_id}?contract_addresses={contract_address_lower}&vs_currencies=usd"
    response = requests.get(url)
    if response.status_code == 200:
        data = json.loads(response.text)
        try:
            return data[contract_address_lower]['usd']
        except KeyError:
            print(f"Token not found on CoinGecko: {contract_address}")
            return None
    else:
        print(f"Failed to fetch data from CoinGecko. Status code: {response.status_code}")
        return None

def get_lp_reserves(lp_address, lp_abi):
    lp_contract = Web3.eth.contract(address=lp_address, abi=lp_abi)
    reserves = lp_contract.functions.getReserves().call()
    return reserves

def get_token_prices(token0_address, token1_address):
    token0_price = fetch_token_price_from_coingecko(token0_address)
    token1_price = fetch_token_price_from_coingecko(token1_address)
    return token0_price, token1_price

def calculate_imbalance_percent(reserves, prices):
    reserve_token0, reserve_token1, _ = reserves
    price_token0, price_token1 = prices
    reserve_token0_usd = (reserve_token0 / (10 ** 18)) * price_token0
    reserve_token1_usd = (reserve_token1 / (10 ** 18)) * price_token1
    average_value = (reserve_token0_usd + reserve_token1_usd) / 2
    percentage_difference = abs((reserve_token0_usd - reserve_token1_usd) / average_value) * 100
    return percentage_difference, reserve_token0_usd, reserve_token1_usd  # Make sure to return all three values

def calculate_imbalance_percent_uint_6_18(reserves, prices):
    reserve_token0, reserve_token1, _ = reserves
    price_token0, price_token1 = prices
    reserve_token0_usd = (reserve_token0 / (10 ** 6)) * price_token0
    reserve_token1_usd = (reserve_token1 / (10 ** 18)) * price_token1
    average_value = (reserve_token0_usd + reserve_token1_usd) / 2
    percentage_difference = abs((reserve_token0_usd - reserve_token1_usd) / average_value) * 100
    return percentage_difference, reserve_token0_usd, reserve_token1_usd  # Make sure to return all three values

def calculate_imbalance_percent_uint_18_6(reserves, prices):
    reserve_token0, reserve_token1, _ = reserves
    price_token0, price_token1 = prices
    reserve_token0_usd = (reserve_token0 / (10 ** 18)) * price_token0
    reserve_token1_usd = (reserve_token1 / (10 ** 6)) * price_token1
    average_value = (reserve_token0_usd + reserve_token1_usd) / 2
    percentage_difference = abs((reserve_token0_usd - reserve_token1_usd) / average_value) * 100
    return percentage_difference, reserve_token0_usd, reserve_token1_usd  # Make sure to return all three values

def calculate_imbalance_percent_uint_6_6(reserves, prices):
    reserve_token0, reserve_token1, _ = reserves
    price_token0, price_token1 = prices
    reserve_token0_usd = (reserve_token0 / (10 ** 6)) * price_token0
    reserve_token1_usd = (reserve_token1 / (10 ** 6)) * price_token1
    average_value = (reserve_token0_usd + reserve_token1_usd) / 2
    percentage_difference = abs((reserve_token0_usd - reserve_token1_usd) / average_value) * 100
    return percentage_difference, reserve_token0_usd, reserve_token1_usd  # Make sure to return all three values

def calculate_imbalance_percent_corgiai_usdc(reserves, prices):
    reserve_token0, reserve_token1, _ = reserves  # Assuming token0 is CorgiAI and token1 is USDC
    price_token0, price_token1 = prices
    reserve_token0_usd = (reserve_token0 / (10 ** 18)) * price_token0  # CorgiAI has 18 decimals
    reserve_token1_usd = (reserve_token1 / (10 ** 6)) * price_token1  # USDC has 6 decimals
    average_value = (reserve_token0_usd + reserve_token1_usd) / 2
    percentage_difference = abs((reserve_token0_usd - reserve_token1_usd) / average_value) * 100
    return percentage_difference, reserve_token0_usd, reserve_token1_usd

def is_lp_balanced(percentage_difference, threshold=0.01):
    return percentage_difference < threshold

def calculate_trade_amount_to_balance_lp(reserve_token0_usd, reserve_token1_usd, token0_price, token1_price):
    imbalance_usd = abs(reserve_token0_usd - reserve_token1_usd)
    # Calculate the amount to trade for each token to balance the LP
    amount_to_trade_token0 = imbalance_usd / 2 / token0_price
    amount_to_trade_token1 = imbalance_usd / 2 / token1_price
    return amount_to_trade_token0, amount_to_trade_token1

def execute_trade(dominant_token, target_token, amount_to_trade, private_key, web3_instance): # works!!!!
    # Initialize Web3
    web3 = web3_instance

    # Router contract address and ABI
    router_address = '0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae'  # Replace with actual address
    router_abi = load_contract_abi('RouterABI.json')  # Replace with actual ABI

    # Initialize contracts
    router_contract = web3.eth.contract(address=router_address, abi=router_abi)

    # Your wallet address
    # print(dir(web3.eth.account))
    my_account = web3.eth.account.from_key(private_key)
    my_address = my_account.address

    # Token contract addresses and ABIs for dominant and target tokens
    dominant_token_address = dominant_token  # Replace with actual address
    target_token_address = target_token  # Replace with actual address
    token_abi = load_contract_abi('VVS_abi.json')  # Replace with actual ABI for both tokens

    # Initialize token contracts
    dominant_token_contract = web3.eth.contract(address=dominant_token_address, abi=token_abi)
    target_token_contract = web3.eth.contract(address=target_token_address, abi=token_abi)

    # Build the transaction for token approval
    approve_txn = dominant_token_contract.functions.approve(
        router_address,
        amount_to_trade
    ).build_transaction({
        'chainId': 25,  # Cronos
        'gas': 159397,
        'gasPrice': web3.to_wei('4676', 'gwei'), # changed the amount of gas
        'nonce': web3.eth.get_transaction_count(my_address),
    })

    # Sign the transaction
    signed_approve_txn = web3.eth.account.sign_transaction(approve_txn, private_key)

    # Send the transaction and wait for it to be mined
    approval_tx_hash = web3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
    web3.eth.wait_for_transaction_receipt(approval_tx_hash)

    # Build the swap transaction
    swap_txn = router_contract.functions.swapExactTokensForTokens(
        amount_to_trade,
        1,  # Minimum amount of target token to receive, set to a reasonable value
        [dominant_token_address, target_token_address],  # Path (dominant_token -> target_token)
        my_address,  # Recipient
        int(time.time()) + 1200  # Deadline
    ).build_transaction({
        'chainId': 25,
        'gas': 159397,
        'gasPrice': web3.to_wei('4676', 'gwei'), # changed the amount of gas
        'nonce': web3.eth.get_transaction_count(my_address),
    })

    # Sign the swap transaction
    signed_swap_txn = web3.eth.account.sign_transaction(swap_txn, private_key)

    # Send the swap transaction
    swap_tx_hash = web3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
    web3.eth.wait_for_transaction_receipt(swap_tx_hash)

def compare_lps(lp1_result, lp2_result):
    if lp1_result['net_profit_usd'] > lp2_result['net_profit_usd']:
        print(f"LP1 with {lp1_result['token0_name']}/{lp1_result['token1_name']} is more profitable for arbitrage.")
        return lp1_result
    else:
        print(f"LP2 with {lp2_result['token0_name']}/{lp2_result['token1_name']} is more profitable for arbitrage.")
        return lp2_result

def get_highest_balance_token(web3, private_key, token_data):

    # Check connection
    if not web3.is_connected():
        print("Not connected to the network")
        return None

    # Set up your account
    account = web3.eth.account.from_key(private_key)
    my_address = account.address

    highest_balance = 0
    highest_balance_token = None

    for token in token_data:
        # Create contract instance
        token_contract = web3.eth.contract(address=token['address'], abi=token['abi'])

        # Fetch balance
        balance_wei = token_contract.functions.balanceOf(my_address).call()
        balance = web3.from_wei(balance_wei, 'ether')

        print(f"Balance of {token['name']}: {balance} tokens")

        if balance > highest_balance:
            highest_balance = balance
            highest_balance_token = token['name']

    return highest_balance_token, highest_balance

def get_token_balance(network_rpc, private_key, token_contract_abi, token_contract_address):
    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider(network_rpc))

    # Check connection
    if not web3.is_connected():
        print("Not connected to the network")
        return None

    # Set up your account
    account = web3.eth.account.from_key(private_key)
    my_address = account.address

    # Create contract instance
    token_contract = web3.eth.contract(address=token_contract_address, abi=token_contract_abi)

    # Fetch balance
    balance_wei = token_contract.functions.balanceOf(my_address).call()
    balance = web3.from_wei(balance_wei, 'ether')

    return balance

def calculate_discount(lp_price, market_price):
    discount = ((lp_price - market_price) / market_price) * 100
    return discount

def write_to_bookkeeping(token_name, profit_in_token, profit_in_usd):
    with open("bookkeeping.txt", "a") as f:
        f.write(f"Token: {token_name}, Profit in Token: {profit_in_token}, Profit in USD: {profit_in_usd}\n")

def get_lp_reserves(lp_address, lp_abi):
    lp_contract = Web3.eth.contract(address=lp_address, abi=lp_abi)
    reserves = lp_contract.functions.getReserves().call()
    return reserves

