import pymongo

# config.py
class Config:
    SECRET_KEY = 'DN0kJdOtj5eJmoo3@cluster0.jzfu1jp.mongodb.net/'
    MONGO_URI = 'mongodb+srv://andresgb2013'


#conexion
#myClient = pymongo.MongoClient("mongodb+srv://andresgb2013:DN0kJdOtj5eJmoo3@cluster0.jzfu1jp.mongodb.net/")
#variable that storage this info in my DB
#myDb = myClient["SD_Project"]
#myCollection = myDb["users"]

#myUser = { "id": "1234567891", "name": "Peter", "LastName": "Jackson", "email": "peterJ@gmail.com", "password": "1234567891", "auth_level":"super"}

#result = myCollection.insert_one(myUser)
#print(result)