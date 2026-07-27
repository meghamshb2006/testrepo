from search.database import SearchDatabase

db = SearchDatabase()

db.initialize()

print("Database initialized successfully!")

db.close()
