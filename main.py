import requests
from bs4 import BeautifulSoup


def lambda_handler(event, context):
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1866.237 Safari/537.36'}
    url = f"https://www.oliveiratrust.com.br/fiduciario/pus_dt.php?ativo=CRI"

    # Setting verify=False is a hack to avoid SSL errors, best to revisit this later:
    response = requests.get(url, headers=header, verify=False)
    soup = BeautifulSoup(response.content, 'html.parser')

    # get a list of all the table rows in the table body:
    table_rows_list = soup.find_all(["tr"])

    # get the header rows:
    headers_list = []
    for headers in table_rows_list[:2]:
        for cell in headers.find_all("td"):
            # Hack to get around the double header row:
            if "Pagamento" or "P.U.(ex)" not in cell.text:
                headers_list.append(cell.text)
    # Add the last header back in:
    headers_list.append("P.U.(ex)")

    # for every table row, starting at the 3rd row (first two are headers), get the information from the columns:
    data = []
    for row in table_rows_list[2:len(table_rows_list)]:
        data_row = []
        for cell, header in zip(row.find_all("td"), headers_list):
            data_row.append({header: cell.text})
        data.append(data_row)

    print(data)
    return data


if __name__ == "__main__":
    lambda_handler(None, None)
