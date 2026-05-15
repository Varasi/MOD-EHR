from health_connector_base.handlers import APIHandler, Response 
import json 
from health_connector_base.constants import Status
from health_connector_base.via import Via
from health_connector_base import SecretsManager
import requests

def validating_rider_handler(event, context):
    body = json.loads(event.get("body",""))
    print("body:", body)

    try:
        rider_details  = Via().get_rider_validation(rider_id=body.get("via_rider_id"), rider_email=body.get("email"), rider_phone=body.get("phone"), first_name=body.get("first_name"), last_name=body.get("last_name"))
        print("rider_details:", rider_details)
        
        if len(rider_details) > 1:
            res_body = {"message": "More than one rider found. Please provide more details"}
        elif len(rider_details) == 1:
            res_body = rider_details[0]
            error_fields = []
            if body.get("via_rider_id") and str(rider_details[0].get("rider_id")) != body.get("via_rider_id"):
                error_fields.append("Via Rider ID")
            if body.get("email") and rider_details[0].get("email_address") != body.get("email"):
                error_fields.append("Email")

            rider_ph = rider_details[0].get("e164_phone_number")
            rider_ph = rider_ph.replace(" ", "")
            rider_ph = rider_ph.replace("-", "")
            print("rider_ph:", rider_ph, "phone:", body.get("phone"))
            if body.get("phone") and rider_ph != body.get("phone"):
                error_fields.append("Phone")
            if body.get("first_name") and rider_details[0].get("first_name") != body.get("first_name"):
                error_fields.append("First_name")
            if body.get("last_name") and rider_details[0].get("last_name") != body.get("last_name"):
                error_fields.append("Last_name")
            field_list = ", ".join(error_fields)
            if len(error_fields)>0:
                res_body = {"message": f"{field_list} fields are incorrect. Please check and try again."}
                return Response(body=res_body,status=Status.HTTP_400_BAD_REQUEST)

        else:
            res_body = {"message": "NoSuchRiderError"}
            return Response(body=res_body,status=Status.HTTP_400_BAD_REQUEST)
        
        return Response(body=res_body,status=Status.HTTP_200_OK)
    except Exception as e:
        print("error:", e)
        try:
            error_data = json.loads(str(e))  # convert string back to dict
            status = error_data.get("status", Status.HTTP_500_INTERNAL_SERVER_ERROR)
            body = error_data.get("message", error_data)
        except Exception:
            # fallback if it's not JSON
            status = Status.HTTP_500_INTERNAL_SERVER_ERROR
            body = {"message": str(e)}

        return Response(
            body=body,
            status=status
        )
    
def get_lat_lng(address):
    secrets_manager = SecretsManager()
    API_KEY = secrets_manager.get_secret_value("google_map_api_key")
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": API_KEY
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        return None, None

def set_trip_request_body(body):
    dest_lat, dest_lng = get_lat_lng(body.get("destination_address", ""))
    pickup_lat, pickup_lng = get_lat_lng(body.get("pickup_address", ""))

    request_body={}
    request_body["additional_passengers"]={}
    if body.get("trip_direction", "") == "To Appointment":
        request_body["arrive_at"]=body.get("appt_time", "")
    else:
        request_body["depart_at"]=body.get("appt_time", "")
    destination = {
        "lat": dest_lat,
        "lng": dest_lng,
        "address": body.get("destination_address", ""),
        "notes": body.get("additional_notes_dropoff", "")
    }
    origin = {
        "lat": pickup_lat,
        "lng": pickup_lng,
        "address": body.get("pickup_address", ""),
        "notes": body.get("additional_notes_pickup", "")
    }
    request_body["destination"] = destination
    request_body["origin"] = origin
    request_body["passenger_count"]=1

    secrets_manager = SecretsManager()
    subservice = secrets_manager.get_secret_value("sub_service_name")

    request_body["sub_service"] = subservice
    if body.get("via_rider_id", ""):
        request_body["rider_id"] = body["via_rider_id"]
    else:
        request_body["passenger_info"]={
            "first_name": body.get("first_name", ""),
            "last_name": body.get("last_name", ""),
            "phone_number": body.get("phone", ""),
            "email": body.get("email", ""),
        }
    trip_properties_list = []
    if body.get("requires_wav", False):
        trip_properties_list.append("WAV")
    if body.get("has_luggage", False):
        trip_properties_list.append("LUGGAGE")
    if len(trip_properties_list) > 0:
        request_body["trip_properties"] = trip_properties_list

    print("request_body:", request_body)

    return request_body

def ride_booking_handler(event, context):
    body = json.loads(event.get("body",""))
    try:

        #reuqest trip
        request_trip_resp = Via().request_new_trip(set_trip_request_body(body))
        print("request_trip_id:", request_trip_resp)
        trip_details = request_trip_resp.get("trips")
        if trip_details:
            request_trip_id = trip_details[0].get("trip_id")
        
            #Book trip
            Booking_resp = Via().book_trip(request_trip_id)
            if Booking_resp.get("trip_status") == "CONFIRMED":

                #get trip details
                trip_details_resp = Via().get_trip_details(request_trip_id)
                print("trip_details_resp:", trip_details_resp)
                return Response(body={"message": "Trip booked successfully", "data": trip_details_resp}, status=Status.HTTP_200_OK)
            

        else:
            error_msg = request_trip_resp.get("message", "Failed to book trip") + request_trip_resp.get("info", "")
            return Response(body={"message": error_msg}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
        
    except Exception as e:
        print("error:", e)
        try:
            error_data = json.loads(str(e))  # convert string back to dict
            status = error_data.get("status", Status.HTTP_500_INTERNAL_SERVER_ERROR)
            body = error_data.get("message", error_data)
        except Exception:
            # fallback if it's not JSON
            status = Status.HTTP_500_INTERNAL_SERVER_ERROR
            body = {"message": str(e)}

        return Response(
            body=body,
            status=status
        )

def lambda_handler(event, context):
    path = event.get("path", "")
    if "validate_patient" in path:
        return validating_rider_handler(event, context)
    elif "trip_booking" in path:
        return ride_booking_handler(event, context)
    
    return Response(body={"message": "Not Found"}, status=Status.HTTP_404_NOT_FOUND)