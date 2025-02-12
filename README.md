# Natural Language Database Query System

Convert natural language questions into SQL queries using AI, with built-in schema validation and error prevention. This system allows you to query your SQL Server database using plain English, powered by OpenAI's GPT-4.

## Overview

This system enables you to:
- Query your database using natural language
- Convert questions into valid SQL automatically
- Prevent common AI hallucination issues through schema validation
- Get results in human-readable format

## Prerequisites

- Python 3.8+
- Microsoft SQL Server
- AdventureWorks sample database ([Download](https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks2022.bak))
- OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/zulkiflifauzi/nldqs
cd nldqs
```

2. Install required packages:
```bash
pip install openai python-dotenv pyodbc sqlite3
```

3. Set up the AdventureWorks database:
   - Download the backup file from the link above
   - Restore it using SQL Server Management Studio
   - Right-click Databases → Restore Database → Choose the .bak file

## Configuration

### 1. Environment Variables
Edit a `.env` file in the project root:

```plaintext
DB_SERVER=your_sql_server
DB_DATABASE=AdventureWorks2022
DB_USERNAME=your_username
DB_PASSWORD=your_password
OPENAI_API_KEY=your_openai_api_key
```
## Usage

1. Run the main script:
```bash
python query_ai.py
```

2. Enter your question when prompted:
```
Ask your database (or 'exit' to quit): Who are the top 5 salespeople by revenue?
```

3. Get your results in both SQL and human-readable format:
```
Generated SQL Query:
SELECT TOP 5 
    p.FirstName, 
    p.LastName, 
    SUM(soh.TotalDue) as TotalRevenue
FROM Sales.SalesPerson sp
JOIN Person.Person p ON p.BusinessEntityID = sp.BusinessEntityID
JOIN Sales.SalesOrderHeader soh ON soh.SalesPersonID = sp.BusinessEntityID
GROUP BY p.FirstName, p.LastName
ORDER BY TotalRevenue DESC

Results:
The top 5 salespeople by revenue are:
1. Linda Mitchell ($4,251,368.55)
2. Jae Pak ($4,116,871.22)
3. Michael Blythe ($3,763,178.18)
4. Jillian Carson ($3,189,418.36)
5. Ranjit Varkey ($3,121,616.73)
```

## Example Queries

Try these queries with the AdventureWorks database:

```plaintext
# Sales Analysis
- What were our total sales for last year?
- Show me the sales trend by quarter
- Which products have the highest profit margin?

# Inventory Management
- Which products are low in stock?
- What's our current inventory value by category?
- Show me products with no sales in the last 6 months

# Employee Queries
- Who has the highest sales in each region?
- What's the average sick leave by department?
- Show me employee turnover by year
```

## Key Features

1. **Schema Validation**
   - Prevents invalid column/table references
   - Maintains database schema cache
   - Validates queries before execution

2. **Natural Language Processing**
   - Uses GPT-4 for query generation
   - Provides human-readable results
   - Handles complex business questions

3. **Error Handling**
   - Comprehensive logging system
   - Clear error messages
   - Connection failure recovery

## Limitations

- Designed for SQL Server (does not support other databases)
- Requires SQL Server Authentication
- Schema changes need cache refresh
- Query complexity limited by GPT-4 capabilities

## Troubleshooting

Common issues and solutions:

1. **Connection Errors**
   - Verify SQL Server credentials in .env
   - Check if SQL Server is running
   - Ensure network connectivity

2. **Schema Validation Errors**
   - Delete schema_cache.db to refresh schema
   - Verify database permissions
   - Check table/column names

3. **OpenAI API Issues**
   - Verify API key in .env
   - Check API quota and limits
   - Ensure internet connectivity

## Contributing

Contributions welcome! Areas for improvement:

- Additional database support
- Query optimization features
- Enhanced schema caching
- UI/API development
- Additional example queries

## License

[Your chosen license]

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review error logs in query_ai.log
3. [Open an issue](your-repository-issues-url)
