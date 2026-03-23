import requests
import time

API_URL = "http://127.0.0.1:5000/gps_ping"

# Change this to the student ID you want to test
STUDENT_ID = 1

def send_gps(lat, lon):
    data = {
        "student_id": STUDENT_ID,
        "latitude": lat,
        "longitude": lon
    }

    try:
        r = requests.post(API_URL, json=data, timeout=5)
        print("Response:", r.json())
    except Exception as e:
        print("Error sending GPS:", e)


if __name__ == "__main__":
    print("=== GPS Test Script Started ===")

    while True:
        print("\n1) Inside campus")
        print("2) Outside campus")
        print("3) Custom location")
        print("4) Exit")

        choice = input("\nChoose an option: ")

        if choice == "1":
            # Example INSIDE campus
            send_gps(26.769900, 75.877600)

        elif choice == "2":
            # Example OUTSIDE campus
            send_gps(26.750000, 75.860000)

        elif choice == "3":
            lat = input("Enter latitude: ")
            lon = input("Enter longitude: ")
            send_gps(float(lat), float(lon))

        elif choice == "4":
            print("Exiting GPS sender.")
            break

        else:
            print("Invalid choice. Try again.")

        time.sleep(1)