# Mongo DB

# Insertion

i) insertOne()

ii) insertMany()

# view or retrieve data

```
i) findOne()  eg:- db.employee.findOne({name : "Rahul"})
ii) find()	eg:- db.employee.find({name : "Rahul"}) or db.employee.find()
iii) find().toArray() eg:- db.employee.find().toArray()
vi) find().forEach()  eg:- db.employee.find().forEach((data)=>{print(data)})
```


projection

v)  db.employee.find({},{name:1})	eg:- to get name and id
vi) db.employee.find({},{name:1,_id:0})	eg:- to get only name
vii) db.employee.find().limit(2)	eg:- to get only 2 data
viii)  db.employee.find().skip(2)	eg:- to get data after 2 data
ix) db.employee.find().sort({name:1})	eg:- to get data in accending order
x) db.employee.find().sort({name:-1})	eg:- to get data in decending order

# query data

## comparative query

xi) db.employee.find({"details.salary":{$eq:30000}}) eg:- to get data of salary equal to 30000
xii) db.employee.find({"details.salary":{$ne:30000}}) eg:- to get data of salary not equal to 30000
xiii) db.employee.find({"details.salary":{$in:[30000,60000,]}}) eg:- to get data of salary which match with value in a array

## logical query

xiv)  db.employee.find({ $and: [{ name: { $eq: 'poda' } }, { "details.salary": { $eq: 30000 } }] } ) eg:- to show when both conditions are true
xv) db.employee.find({ $or: [{ name: { $eq: 'poda' } }, { "details.salary": { $eq: 30000 } }] } ) eg:- to show when only one conditions are true

## update data

i) updateOne()  eg:- db.employee.updateOne({name:"Daniel"},{$set:{"details.position":"PHP Developer"}})

ii) updateMany() eg:- db.employee.updateOne({name:"Daniel"},{$set:{"details.position":"PHP Developer"}})

## Delete

i) deleteOne()  eg:-db.employee.deleteOne({name:"Daniel"})
ii) deleteMany()  eg:-db.employee.deleteMany({"details.position":"PHP Developer"})

# comparative logic in db

```q
{$gt:value} eg:- db.employee.find({"details.salary":{$gt:50000}})
```
## greater than or equal

```q
{$gte:vale} eg:- db.employee.find({"details.salary":{$gte:50000}})
```

## lesser than

```q
{$lt:value} eg:- db.employee.find({"details.salary":{$lt:50000}})
```

## lesser than or equal

```q
{$lte:value} eg:- db.employee.find({"details.salary":{$lte:50000}})
```

## get the collection of matching data in a array

```q
{$in:[valu1,value2,value3]} eg:- db.employee.find({age:{$in:[28,38,40]}})
```

## regular expression

i)db.employee.find({name:{$regex:"^s"})  eg: to get details with starting letter
ii)db.employee.find({name:{$regex:"^s",$options:"i"}}) eg: to get details with starting letter without case sensitive

## return fuction in mongo db

```q
db.employee.find({$where:function(){return this.name=="sanjay"; }})
```



Sorting of data

i) db.employee.find().sort({name:1}) eg: to get details in assending order
ii) db.employee.find().sort({name:-1}) eg: to get details in decending  order

# mongo db in  node js using express

## to create a node js server with mango db

i) npm i --s express express-handlebars body-parser
ii)  npm i -g nodemon

iii) nodemon app.js  - to run the node js in local host
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser  eg:- run this command if any nodemon shows security error