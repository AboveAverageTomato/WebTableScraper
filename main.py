import requests
from bs4 import BeautifulSoup


def lambda_handler(event, context):
    # Header not strictly necessary
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1866.237 Safari/537.36'}
    url = f"https://www.oliveiratrust.com.br/fiduciario/pus_dt.php?ativo=CRI"

    # Setting verify=False is a hack to avoid SSL errors, best to revisit and fix this later:
    response = requests.get(url, headers=header, verify=False)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Get a list of all the table rows in the table body:
    table_rows_list = soup.find_all(["tr"])

    # Get the header rows:
    headers_list = []
    for headers in table_rows_list[:2]:
        for cell in headers.find_all("td"):
            # Fix the double header row:
            if "Pagamento" or "P.U.(ex)" not in cell.text:
                headers_list.append(cell.text)
    # Add the last header back in:
    headers_list.append("P.U.(ex)")

    # For every table row, starting at the 3rd row (first two are headers), get the information from the columns:
    data = []
    for row in table_rows_list[2:len(table_rows_list)]:
        data_row = []
        # Combine the 11 header fields with the values:
        for cell, header in zip(row.find_all("td"), headers_list):
            data_row.append({header: cell.text})
        data.append(data_row)

    print(data)
    return data
