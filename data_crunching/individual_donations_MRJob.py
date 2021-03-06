# CS123
# Campaign Donation MRJob Project

# This file takes a JSON of resolved entities of the form {instance:
# authoritative_name}, reads the full dataset, then extracts relevant 
# information for each authoritative name and prints to csv format.

from mrjob.job import MRJob
from mrjob.protocol import RawValueProtocol
import csv
from fuzzywuzzy import fuzz
import json
import re
import os
import unicodedata

# Column indices for slicing
ID = 0
AMOUNT = 8
DATE = 9
CONTRIBUTOR_NAME = 10
CONTRIBUTOR_TYPE = 12
CONTRIBUTOR_EMPLOYER = 14
ORGANIZATION = 21
PARENT_ORGANIZATION = 23
RECIPIENT_NAME = 25
CANDIDATE_PARTY = 27
SEAT = 36
RESULT = 41

class build_corporate_donations(MRJob):
    '''
    This job builds a dataset for corporate donations.
    '''

    OUTPUT_PROTOCOL = RawValueProtocol

    def configure_options(self):
        '''
        Makes a file available to mapper.
        
        Use: Add --ancillary='FILE-PATH' as an option when running MRJob.
        '''
        super(build_corporate_donations, self).configure_options()
        self.add_file_option('--ancillary')
    
    def byteify(self, data):
        '''
        Converts input to bytes from unicode. 
        
        Many thanks to Mirec Miskuf, who provided this code on Stack Overflow.
        http://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-ones-from-json-in-python
        '''
        if isinstance(data, unicode):
            return data.encode('utf-8')
        if isinstance(data, dict):
            return {self.byteify(key): self.byteify(value) for key, value in data.iteritems()}
    
    def similarity_score(self, string1, string2):
        '''
        Performs an analysis to determine the similarity of two strings.
        '''
        stopwords = [ 'a', 'in', 'for', 'and', 'the', 'as', 'at', 'by', 
         'from', 'into', 'to', 'of', 'on', 'off', 'our', 'that', 
         'so', 'own', 'out', 'communication', 'communications' ,'inc', 
         'incorporated', 'company', 'corporation', 'co', 
         'enterprise', 'enterprises','group', 'industries', 'corp', 'llc', 
         'llp', 'international', 'product', 'products'   
         'technologies', 'technology', 'holdings', 'holding', 'global', 
         'financial', 'service', 'services', 'resource', 'resources']
        string1 = re.sub('[^a-zA-Z\d\s]','',string1).lower()
        string2 = re.sub('[^a-zA-Z\d\s]','',string2).lower()
        string1 = [word for word in string1.split() if word not in stopwords]
        string2 = [word for word in string2.split() if word not in stopwords]
        string1 = "".join(string1)
        string2 = "".join(string2)
        return fuzz.ratio(string1, string2)
    
    def fields(self, line):
        '''
        Reads and strips line.
        '''
        yield_value = False
        try:
            line.encode('ascii', 'ignore')
            # Reads line & eliminates weird characters, skips header
            rdr = csv.reader([line])
            columns = rdr.next()
            for i in range(len(columns)):
                columns[i] = columns[i].replace("'", "").upper()
                columns[i] = columns[i].replace("\\", "")
                columns[i] = columns[i].replace('"', '')
                columns[i] = columns[i].replace('/', '')
            if columns[0] != 'id':
                donor_name = columns[CONTRIBUTOR_NAME].strip()
                donor_name = donor_name.replace(',', '')
                organization = columns[CONTRIBUTOR_EMPLOYER].strip()
                parent = columns[PARENT_ORGANIZATION].strip()
                recipient = columns[RECIPIENT_NAME].strip()
                recipient = recipient.replace('(D)', '')
                recipient = recipient.replace('(R)', '')
                recipient = recipient.replace(',', '')
                recipient = recipient.strip()
                party = columns[CANDIDATE_PARTY].strip()
                date = columns[DATE].strip()
                amount = columns[AMOUNT].strip()
                seat = columns[SEAT].strip()
                result = columns[RESULT].upper().replace("T", "").strip()                
            else:
                donor_name = None
                organization = None
                parent = None
                recipient = None
                party = None
                date = None
                amount = None
                seat = None
                result = None
                
            if organization in self.entity_dictionary: 
                organization = self.entity_dictionary.get(organization)
                organization = organization.replace(',', '')
            else: 
                organization = None
            if parent in self.entity_dictionary:
                parent = self.entity_dictionary.get(parent)
                parent = parent.replace(',', '')
            else:
                parent = None
            
        except Exception as e: 
            donor_name = None
            parent = None
            organization = None
            recipient = None
            party = None
            date = None
            amount = None
            seat = None
            result = None
        
        return (organization, parent, recipient, party, date, amount, seat, result, donor_name)
    
    def mapper_init(self):
        '''
        Holds entity dictionary in memory for authoritative name lookup.
        '''
        with open(self.options.ancillary, 'rU') as f:
            self.entity_dictionary = json.load(f, object_hook = self.byteify)
    
    def mapper(self, _, line):
        '''
        Reads line and concats strings. 
        '''
        organization, parent, recipient, party, date, amount, seat, result, donor_name = self.fields(line)
        
        if organization != None or parent != None:
            score = None
            if organization != None and donor_name != None:
                score = self.similarity_score(donor_name, organization)
            if parent != None and donor_name != None: 
                score = self.similarity_score(donor_name, parent)
            if score and score < 90:
                if date != '':
                    year = date.split('-')[0]
                    month = date.split('-')[1]
                else: 
                    year = 'NaN'
                    month = 'NaN'
                name = [donor_name, organization, parent, recipient, party, seat, result, month, year, str(amount)]
                for i in range(len(name)):
                    if name[i] == None: 
                        name[i] = 'NaN'
                rv = ','.join(name)
                if not (donor_name == 'BAILEY JEROME H' and str(amount) != '25000.00000.00.00'):
                    yield None, rv
        
if __name__ == '__main__':
    build_corporate_donations.run()
