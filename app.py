import random
import string
import smtplib
import os
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import uuid
from tinydb import Query
from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, EmailStr
from typing import List
from datetime import datetime

from db import db

app = FastAPI()

# load .env file
load_dotenv()


class UserInfo(BaseModel):
    fullName: str = Field(...)
    email: EmailStr = Field(...)
    organization: str = Field(...)
    country: str = Field(...)
    approvalStatus: str = Field(...)
    receiveEmails: str = Field(...)
    productTitle: str = Field(...)
    subject: str = Field(...)
    description: str = Field(...)


class UserInfoWrapper(BaseModel):
    userInfo: UserInfo = Field(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "userInfo": {
                    "fullName": "Omar Ilias",
                    "email": "omarilias.elmimouni@nist.gov",
                    "organization": "NIST",
                    "country": "United States",
                    "approvalStatus": "Pending",
                    "receiveEmails": "True",
                    "productTitle": "Data from: Collaborative Guarded-Hot-Plate Tests between the National Institute of Standards and Technology and the National Physical Laboratory",
                    "subject": "RPA: ark:\\88434\\mds2\\2106",
                    "description": "Product Title:\n  Data from: Collaborative Guarded-Hot-Plate Tests between the National Institute of Standards and Technology and the National Physical Laboratory \n\n Purpose of Use: \nLearning and Research"
                }
            }
        }


class UpdateRecordModel(BaseModel):
    Approval_Status__c: str = Field(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {"example": {"Approval_Status__c": "approved"}}


class EmailInfo(BaseModel):
    recordId: str = Field(...)
    recipient: EmailStr = Field(...)
    subject: str = Field(...)
    content: str = Field(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "recordId": "bca9a7508cda11eda5b42a58cc9fff89",
                "recipient": "elmimouni.o.i@gmail.com",
                "subject": "Test email",
                "content": """<h1>Test Email</h1>
                              <div>Congratulations, it is working.</div>
                           """,
            }
        }


def get_case_num():
    case_num = "".join(random.choices(
        string.ascii_letters + string.digits, k=16))
    return case_num


def get_id():
    id = uuid.uuid1()
    return id.hex


@app.post("/services/apexrest/system/V1.0/pdrcasecreate", response_description="Add new record")
async def create_record(user_info_wrapper: UserInfoWrapper = Body(...)):
    new_record = jsonable_encoder(user_info_wrapper)
    new_record["id"] = get_id()
    new_record["caseNum"] = get_case_num()
    db.insert(new_record)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"record": new_record})


@app.get("/services/apexrest/system/V1.0/pdrcasegetall", response_description="List all records")
async def list_records():
    records = db.all()
    return records


@app.get("/services/apexrest/system/V1.0/pdrcaseget/{id}", response_description="Get a single record")
async def show_record(id: str):
    Record = Query()
    if (record := db.get(Record.id == id)) is not None:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"record": record})
    raise HTTPException(status_code=404, detail=f"Record {id} not found")


def set_nested(path, val):
    def transform(doc):
        current = doc
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = val

    return transform


@app.patch("/services/apexrest/system/V1.0/pdrcaseupdate/{id}", response_description="Update a record")
async def update_record(id: str, update: UpdateRecordModel = Body(...)):
    Record = Query()
    if (record := db.search(Record.id == id)) is not None:
        update = jsonable_encoder(update)
        db.update(set_nested(["userInfo", "approvalStatus"],
                  update["Approval_Status__c"]), Record.id == id)
        update["recordId"] = id
        if (record := db.get(Record.id == id)) is not None:
            return JSONResponse(status_code=status.HTTP_200_OK,
                                content={"recordId": id, "approvalStatus": record["userInfo"]["approvalStatus"]})
    raise HTTPException(status_code=404, detail=f"Record {id} not found")


@app.delete("/{id}", response_description="Delete a record")
async def delete_record(id: str):
    Record = Query()
    removed = db.remove(Record.id == id)
    if removed is not None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise HTTPException(status_code=404, detail=f"Record {id} not found")


async def send_email(recipients, subject, content):
    smtp_server = "smtp.gmail.com"
    port = 587  # For starttls
    sender = os.getenv("GMAIL_USER")  # Sender email
    password = os.getenv("GMAIL_PASSWORD")  # Sender password
    sent = {}
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipients
        # msg["To"] = ", ".join(recipients)
        html_content = MIMEText(content, "html")
        msg.attach(html_content)

        sent = server.sendmail(sender, recipients, msg.as_string())
    except Exception as e:
        print(e)
    finally:
        server.quit()
    return sent


@app.post("/services/apexrest/system/V1.0/pdremail", response_description="Send an email")
async def create_record(email_info: EmailInfo = Body(...)):
    email_info = jsonable_encoder(email_info)
    if not await send_email(email_info["recipient"], email_info["subject"], email_info["content"]):
        response = {
            "timestamp": str(datetime.timestamp(datetime.now())),
            "email": {
                "recordId": email_info["recordId"],
                "subject": email_info["subject"],
                "recipient": email_info["recipient"],
                "content": email_info["content"]
            }
        }
        return JSONResponse(status_code=status.HTTP_200_OK, content=response)
    raise HTTPException(status_code=502, detail=f"Could not send email.")
