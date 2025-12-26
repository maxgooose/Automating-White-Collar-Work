class Torque:





    def findTorque( self, from_location, to_location,IMEI,parse_data):
        
        seenTorque = {}


        for i, data in enumerate(parse_data):



                
            if data['imei'] in seenTorque:
                
