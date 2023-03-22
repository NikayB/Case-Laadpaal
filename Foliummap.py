#import voor alle benodigde libraries
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
import seaborn as sns
import plotly.express as px
from sodapy import Socrata
import folium
import streamlit as st
from streamlit_folium import folium_static

#Inladen API chargemap
response = requests.get("https://api.openchargemap.io/v3/poi/?output=json&countrycode=NL&maxresults=1000&compact=true&verbose=false&key=6686970f-0aa6-4cb5-ae81-cf8f6389a816")

#Omzetten naar dictionary
responsejson  = response.json()

#Dataframe bevat kolom die een list zijn. 
#Met json_normalize zet je de eerste kolom om naar losse kolommen
charge_map = pd.json_normalize(responsejson)

charge_map_df = pd.DataFrame.from_records(charge_map)

#Dropping unnecessary columns:
charge_map_df = charge_map_df.drop(columns=['IsRecentlyVerified', 'UUID', 'DataProviderID', 'AddressInfo.CountryID', 
                            'AddressInfo.DistanceUnit', 'AddressInfo.RelatedURL', 'AddressInfo.ContactTelephone1', 
                            'AddressInfo.ContactEmail', 'AddressInfo.ContactTelephone2', 'OperatorsReference', 
                            'DataProvidersReference', 'GeneralComments', 'AddressInfo.AddressLine2',
                            'AddressInfo.AccessComments'
                            ])

#Renaming column names:
charge_map_df.rename(columns={'AddressInfo.Latitude':'LAT', 'AddressInfo.Longitude':'LON', 
                              'AddressInfo.Postcode':'Postcode', 'AddressInfo.ID':'Address_ID', 
                              'AddressInfo.Title':'Address_Title', 'AddressInfo.AddressLine1':'Address_Line1',
                              'AddressInfo.StateOrProvince':'Address_StateOrProvince', 
                              'AddressInfo.Town':'Address_Town'},
                              inplace=True)                            

#Outliers in LAT zijn onder de 50
charge_map_df[charge_map_df['LAT'] < 50]

#Drop de outlier
charge_map_df = charge_map_df.drop(charge_map_df[charge_map_df['LAT'] < 50].index)

# charge_map_df.isna().sum()
#We zien dat UsageTypeID en Address_StateOrProvince meer dan 80% NaN hebben, die filteren we eruit.
charge_map_df = charge_map_df.drop(columns=['UsageTypeID', 'Address_StateOrProvince'])

# charge_map_df['StatusTypeID'].value_counts()
# charge_map_df['SubmissionStatusTypeID'].value_counts()

charge_map_df = charge_map_df.drop(columns=['OperatorID', 'Connections', 'StatusTypeID', 'SubmissionStatusTypeID'])

#Dropping empty values
charge_map_df = charge_map_df.drop(charge_map_df[charge_map_df['Postcode']==''].index)
charge_map_df = charge_map_df.drop(charge_map_df[charge_map_df['Postcode']=='XG'].index)
charge_map_df = charge_map_df.dropna(subset=['Postcode'])

#Transforming the Postcode to Integers
charge_map_df['Postcode'] = charge_map_df['Postcode'].astype(str)
charge_map_df['Postcode'] = charge_map_df['Postcode'].str[0:4]
charge_map_df['Postcode'] = charge_map_df['Postcode'].astype(int)


charge_map_df = charge_map_df.drop(charge_map_df[charge_map_df['Postcode'] < 1000].index)

#Creating address types to make color coding possible.

#Observerd types:
#-Restaurants   = MCDonald's / Mc Donald's,
#-Recreatie     = hotel, Gelredome
#-Parkeren      = P+R, parkeerterrein
#-Tankstations  = Fastned, Supercharger (Tesla),

#Recreation type
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Hotel', case=False), 'Address_Type'] = 'Recreatie'
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Gelredome', case=False), 'Address_Type'] = 'Recreatie'

#Tankstation type
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Fastned', case=False), 'Address_Type'] = 'Tankstation'
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Supercharger', case=False), 'Address_Type'] = 'Tankstation'
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Shell', case=False), 'Address_Type'] = 'Tankstation'
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('IONITY', case=False), 'Address_Type'] = 'Tankstation'

#Restaurants type
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Mc Donald', case=False), 'Address_Type'] = 'Restaurant'
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('McDonald', case=False), 'Address_Type'] = 'Restaurant'
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Restaurant', case=False), 'Address_Type'] = 'Restaurant'

#Parkeerplaats type
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Parkeer', case=False), 'Address_Type'] = 'Parkeerterrein'
charge_map_df.loc[charge_map_df['Address_Title'].str.contains('Garage', case=False), 'Address_Type'] = 'Parkeerterrein'

#Filling in the NaNs with 'Straat'
charge_map_df['Address_Type'].fillna('Straat', inplace=True)

def color_type(type):
    if type == 'Recreatie':
        return 'green'
    elif type == 'Straat':
        return 'blue'
    elif type == 'Tankstation':
        return 'black'
    elif type == 'Restaurant':
        return 'orange'
    elif type =='Parkeerterrein':
        return 'darkblue'

#Test code
color_type(charge_map_df['Address_Type'][3])

#Dropping outliers that were made with typos in LAT &| LON
typos = [364, 4947, 1414, 1203, 5479, 1351, 2387, 1242, 479, 1882, 1597, 2413, 2064, 1670, 1941, 1982, 4094, 2831, 7198]

charge_map_df = charge_map_df.drop(index= typos)

charge_map_df['NumberOfPoints'] = charge_map_df['NumberOfPoints'].astype(int).astype(str)

#Add_categorical_legend
def add_categorical_legend(folium_map, title, colors, labels):
    if len(colors) != len(labels):
        raise ValueError("colors and labels must have the same length.")

    color_by_label = dict(zip(labels, colors))
    
    legend_categories = ""     
    for label, color in color_by_label.items():
        legend_categories += f"<li><span style='background:{color}'></span>{label}</li>"
        
    legend_html = f"""
    <div id='maplegend' class='maplegend'>
      <div class='legend-title'>{title}</div>
      <div class='legend-scale'>
        <ul class='legend-labels'>
        {legend_categories}
        </ul>
      </div>
    </div>
    """
    script = f"""
        <script type="text/javascript">
        var oneTimeExecution = (function() {{
                    var executed = false;
                    return function() {{
                        if (!executed) {{
                             var checkExist = setInterval(function() {{
                                       if ((document.getElementsByClassName('leaflet-top leaflet-right').length) || (!executed)) {{
                                          document.getElementsByClassName('leaflet-top leaflet-right')[0].style.display = "flex"
                                          document.getElementsByClassName('leaflet-top leaflet-right')[0].style.flexDirection = "column"
                                          document.getElementsByClassName('leaflet-top leaflet-right')[0].innerHTML += `{legend_html}`;
                                          clearInterval(checkExist);
                                          executed = true;
                                       }}
                                    }}, 100);
                        }}
                    }};
                }})();
        oneTimeExecution()
        </script>
      """
   

    css = """

    <style type='text/css'>
      .maplegend {
        z-index:9999;
        float:right;
        background-color: rgba(255, 255, 255, 1);
        border-radius: 5px;
        border: 2px solid #bbb;
        padding: 10px;
        font-size:12px;
        positon: relative;
      }
      .maplegend .legend-title {
        text-align: left;
        margin-bottom: 5px;
        font-weight: bold;
        font-size: 90%;
        }
      .maplegend .legend-scale ul {
        margin: 0;
        margin-bottom: 5px;
        padding: 0;
        float: left;
        list-style: none;
        }
      .maplegend .legend-scale ul li {
        font-size: 80%;
        list-style: none;
        margin-left: 0;
        line-height: 18px;
        margin-bottom: 2px;
        }
      .maplegend ul.legend-labels li span {
        display: block;
        float: left;
        height: 16px;
        width: 30px;
        margin-right: 5px;
        margin-left: 0;
        border: 0px solid #ccc;
        }
      .maplegend .legend-source {
        font-size: 80%;
        color: #777;
        clear: both;
        }
      .maplegend a {
        color: #777;
        }
    </style>
    """

    folium_map.get_root().header.add_child(folium.Element(script + css))

    return folium_map

st.write(charge_map_df.head())

#Generating the map
map = folium.Map(location=[52.0893191, 5.1101691], zoom_start=8)
# st_map = folium_static(map)

# Define dictionaries to store postcode ranges and corresponding map objects
postcode_ranges = {
    (1000, 2000): folium.FeatureGroup(name='Postcode 1000-1999', show=True),
    (2000, 3000): folium.FeatureGroup(name='Postcode 2000-2999', show=False),
    (3000, 4000): folium.FeatureGroup(name='Postcode 3000-3999', show=False),
    (4000, 5000): folium.FeatureGroup(name='Postcode 4000-4999', show=False),
    (5000, 6000): folium.FeatureGroup(name='Postcode 5000-5999', show=False),
    (6000, 7000): folium.FeatureGroup(name='Postcode 6000-6999', show=False),
    (7000, 8000): folium.FeatureGroup(name='Postcode 7000-7999', show=False),
    (8000, 9000): folium.FeatureGroup(name='Postcode 8000-8999', show=False),
    (9000, 10000): folium.FeatureGroup(name='Postcode 9000-9999', show=False)
    }

post_all = folium.FeatureGroup(name="Alle postcodes", show=False).add_to(map)

# Iterate through rows of the DataFrame and add markers to corresponding postcode range maps
for index, row in charge_map_df.iterrows():
    postcode = row['Postcode']
    for postcode_range, postcode_map in postcode_ranges.items():
        if postcode_range[0] <= postcode < postcode_range[1]:
            postcode_map.add_child(folium.CircleMarker(location=[row['LAT'], row['LON']], popup=folium.Popup('<b>' + row['Address_Title'] + '</b><br>' + 'Aantal connecties: ' + row['NumberOfPoints'], min_width=100, max_width=100), radius=6, color=color_type(row['Address_Type']), fill=True, fill_color = color_type(row['Address_Type'])).add_to(postcode_map))
            break

# Add all postcode range maps to the main map
for postcode_map in postcode_ranges.values():
    map.add_child(postcode_map)
    
for index, row in charge_map_df.iterrows():
    if row['Postcode'] > 0:
      post_all.add_child(folium.CircleMarker(location=[row['LAT'], row['LON']], popup=folium.Popup('<b>' + row['Address_Title'] + '</b><br>' + 'Aantal connecties: ' + row['NumberOfPoints'], min_width=100, max_width=100), radius=6, color=color_type(row['Address_Type']), fill=True, fill_color = color_type(row['Address_Type'])).add_to(map))

# #Adding legend
# map = add_categorical_legend(map, 'Locatie laadpunten',
#                              colors = ['blue', 'green', 'black', 'orange', 'darkblue'],
#                              labels = ['Straat', 'Recreatie', 'Tankstation', 'Restaurant', 'Parkeerterrein']
#                              )

# Layer control toevoegen zodat de postcode te selecteren is
folium.LayerControl(position='bottomleft', collapsed=False).add_to(map)

