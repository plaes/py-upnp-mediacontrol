#! /usr/bin/env python3
import cgi
import re
import requests
import socket
import sys
from urllib import parse
from xml.etree import ElementTree

AV_Transport_XML = """POST {endpoint} HTTP/1.1
Accept: application/json, text/plain, */*
Soapaction: "urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"
Content-Type: text/xml;charset="UTF-8"

<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <CurrentURI>{uri}</CurrentURI>
      <CurrentURIMetaData>{didl_lite}</CurrentURIMetaData>
    </u:SetAVTransportURI>
  </s:Body>
</s:Envelope>"""

AV_PlayTemplate = """POST {endpoint} HTTP/1.1
Accept: application/json, text/plain, */*
Soapaction: "urn:schemas-upnp-org:service:AVTransport:1#Play"
Content-Type: text/xml;charset="UTF-8"

<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:Play>
  </s:Body>
</s:Envelope>"""

AV_StopTemplate = """POST {endpoint} HTTP/1.1
Accept: application/json, text/plain, */*
Soapaction: "urn:schemas-upnp-org:service:AVTransport:1#Stop"
Content-Type: text/xml;charset="UTF-8"

<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
    </u:Stop>
  </s:Body>
</s:Envelope>"""


def build_didl_lite(uri):
    tmpl = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:sec="http://www.sec.co.kr/">
 <item id="f-0" parentID="0" restricted="0">
   <upnp:class>object.item.videoItem</upnp:class>
   <res protocolInfo="http-get:*:video/mp4:DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000" sec:URIType="public">{uri}</res>
 </item>
</DIDL-Lite>""".format(uri=uri)
    return cgi.escape(tmpl).replace('\n', "")

def send_message(ip, port, msg):
    #print (ip, port)
    #print ("\n===\n{msg}\n===\n".format(msg=msg))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    s.connect((ip, port))
    sent = s.send(msg.replace("\n", "\r\n").encode('ASCII'))
    if (sent <= 0):
        s.close()
        return
    recv = s.recv(10000)
    #print (recv)
    s.close()

def discover_pnp_locations(service):
    locations = set()
    location_regex = re.compile("location: (.+)\r\n", re.IGNORECASE)
    ssdpDiscover = ('M-SEARCH * HTTP/1.1\r\n' +
                    'HOST: 239.255.255.250:1900\r\n' +
                    'MAN: "ssdp:discover"\r\n' +
                    'MX: 3\r\n' +
                    'ST: {}\r\n'.format(service) +
                    '\r\n')
    print (ssdpDiscover)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ssdpDiscover.encode('ASCII'), ("239.255.255.250", 1900))
    sock.settimeout(1)
    try:
        while True:
            data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
            location_result = location_regex.search(data.decode('ASCII'))
            if location_result:
                    locations.add(location_result.group(1))
    except socket.error:
        sock.close()

    return locations

if __name__ == '__main__':
    service = "urn:schemas-upnp-org:service:AVTransport:1"
    results = discover_pnp_locations(service)
    # TODO... go through all results and look up mediacontrol endpoint

    # Take first element from locations
    endpoint = next(iter(results))
    # Fetch Service's ControlURL and eventSubURL (SCPDURL)
    resp = requests.get(endpoint)
    # print (resp.text)
    # Parse XML
    tree = ElementTree.fromstring(resp.content)
    ns = {"ns":"urn:schemas-upnp-org:device-1-0"}
    # Look up AVTransport service endpoints
    control_endpoint = None
    for service in tree.findall('ns:device/ns:serviceList/ns:service', ns):
        sid = service.find('ns:serviceId', ns)
        if sid.text != 'urn:upnp-org:serviceId:AVTransport':
            continue
        controlURL = service.find('ns:controlURL', ns)
        if controlURL is None:
            continue
        control_endpoint = controlURL.text

    # parse args...
    # TODO: if more than two endpoints.. raise error... (?)
    media_uri = sys.argv[1]
    o = parse.urlparse(endpoint)
    # XXX: Set media URL ...
    media_request = AV_Transport_XML.format(endpoint=control_endpoint, uri=media_uri, didl_lite=build_didl_lite(media_uri))
    send_message(o.hostname, o.port, media_request)
    # ... and start playing
    send_message(o.hostname, o.port, AV_PlayTemplate.format(endpoint=control_endpoint))
    # XXX: Stop event
    #send_message(o.hostname, o.port, AV_StopTemplate.format(endpoint=control_endpoint))
