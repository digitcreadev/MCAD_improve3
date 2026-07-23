USE [master];
GO
IF DB_ID(N'AdventureWorksDW2022') IS NOT NULL
BEGIN
    ALTER DATABASE [AdventureWorksDW2022] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
END
GO
RESTORE DATABASE [AdventureWorksDW2022]
FROM DISK = N'/var/opt/mssql/backup/AdventureWorksDW2022.bak'
WITH
    MOVE N'AdventureWorksDW2022' TO N'/var/opt/mssql/data/AdventureWorksDW2022.mdf',
    MOVE N'AdventureWorksDW2022_log' TO N'/var/opt/mssql/data/AdventureWorksDW2022_log.ldf',
    REPLACE,
    RECOVERY,
    STATS = 5;
GO
ALTER DATABASE [AdventureWorksDW2022] SET MULTI_USER;
GO
SELECT TOP (5) CalendarYear FROM AdventureWorksDW2022.dbo.DimDate ORDER BY CalendarYear;
GO
SELECT COUNT_BIG(*) AS FactInternetSalesRows FROM AdventureWorksDW2022.dbo.FactInternetSales;
GO
