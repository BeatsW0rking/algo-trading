from processOHLC import * 

start = datetime(2017, 1, 1) #datetime(2024, 8, 31) 
# start = datetime(2024, 8, 20) #2023-11-23 2023-03-18
end = datetime(2024, 11, 23) #datetime(2024, 8, 31)
instrument = 'NAS100_USD'

# runProcessRawPipeline()

clearOHLCTable()


Generate6HourlyOHLC(instrument, start, end, False)

GenerateWeeklyOHLC(instrument, start, end)

GenerateDailyOHLC(instrument, start, end)

GenerateHourlyOHLC(instrument, start, end)

Generate4HourlyOHLC(instrument, start, end, True)
Generate4HourlyOHLC(instrument, start, end, False) # For Indexes and Futures with H4 Alinged to 18:00

minutes = 15
GenerateMinuteOHLC(instrument, start, end, minutes)
minutes = 5
GenerateMinuteOHLC(instrument, start, end, minutes)
# minutes = 2
# GenerateMinuteOHLC(instrument, start, end, minutes)
minutes = 1
GenerateMinuteOHLC(instrument, start, end, minutes)

