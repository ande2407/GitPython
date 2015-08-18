
import subprocess
import time
import sys
import datetime

# save stdout
oldstdout = sys.stdout

def ReadRegisterByte(reg):
	# save stdout
	oldstdout = sys.stdout

	# call i2cget on the register (read as byte)
	R = subprocess.Popen(('i2cget', '-y', '0', '0x64', str(reg), 'b'), stdout=subprocess.PIPE)
	Routput = R.stdout.read()
	#R.wait()

	# return just the value, not the preamble or end. Should be 2 chars long [0xAB\n]. The 0 lets it be interpreted as hex
	val = int(Routput[:4], 0)

	#restore stdout
	sys.stdout = oldstdout

	return val

def ProgramRegister(reg, value):

	P = subprocess.Popen(('i2cset', '-y', '0', '0x64', str(reg), str(value), 'b'))
	P.wait()

	print "\tRegister %d set to %d" % (reg, value)

	return

def CalibrateBattery():

	print "Calibration mode, Initialize Threshold Registers"
	# call i2cset on the Charge Threshold Registers
	# Total range of coulomb counter is: 3355 - > 62180 for 10Ah bat.

	print "Accumulated Charge High: 62180"
	ProgramRegister(0x04, 0xF2)
	ProgramRegister(0x05, 0xE4)
	print "Accumulated Charge Low: 3355"
	ProgramRegister(0x06, 0x0D)
	ProgramRegister(0x07, 0x1B)

	filename = time.ctime() + '_BatteryCalibrationLog.txt'
	with open(filename, "wb") as myfile:
			#create new file each run
			s = 'Minutes Index' + ' | ' + 'Status Register' + ' | ' + 'Accumulated Charge' + ' | ' + 'Voltage' + ' | ' + 'Current' + '\n'
			myfile.write(s)

	# Now we loop. If AC value is greater than CTH, reprogram CTH. If AC is less than CTL, reprogram CTL
	while True:
		# time we execute the read - minute indexed
		dt = (int((time.time() - start) / 60))

		print '\nCurrent Values'
		# grab current flow rate
		current_H = ReadRegisterByte(0x0E)
		current_L = ReadRegisterByte(0x0F)
		cur = float((current_H << 8) + current_L)
		current = (.05/.025) * ((cur - 32767)/32767)
		print "\tCurrent %.2f" % current
		# grab voltage reading from last loop
		volt_H = ReadRegisterByte(8)
		volt_L = ReadRegisterByte(9)
		adc = float((volt_H << 8) + volt_L)
		voltage = (23.6 * (adc/65535))
		print "\tVoltage: %.2f" % (voltage)
		# get control register.
		# get charge value
		valHigh = ReadRegisterByte(2)
		valLow = ReadRegisterByte(3)
		charge = (valHigh << 8) + valLow
		print "\tCharge is: %d" % (charge)
		# get high threshold
		CTH_H = ReadRegisterByte(4)
		CTH_L = ReadRegisterByte(5)
		CTH = (CTH_H << 8) + CTH_L
		print "\tCTH is: %d" % (CTH)
		# get low threshold
		CTL_H = ReadRegisterByte(6)
		CTL_L = ReadRegisterByte(7)
		CTL = (CTL_H << 8) + CTL_L
		print "\tCTL is: %d" % (CTL)
		# get status register. Check for overflows
		status = ReadRegisterByte(0)
		if status & 0x40:
			# overflow - Not sure what to do with it?
			CURRENT_ALARM = "Overflow!!!"
		elif status & 0x08:
			# high limit
			CURRENT_ALARM = "high limit exceeded - Reset Threshold"
		elif status & 0x04:
			# low limit
			CURRENT_ALARM = "Low limit exceeded - stay here until we are actually dead?"
		elif status & 0x02:
			# low voltage alarm. Shut down now!

			CURRENT_ALARM =  "Low Voltage detected: %.2f" % voltage
			with open(filename, "ab") as myfile:
				s = '%d, %d, %d, %.3f, %.3f\n' %(dt, status, charge, voltage, current)
				if CURRENT_ALARM:
					s += CURRENT_ALARM + '\n'
				myfile.write(s)

			# shut down here.
			subprocess.call(('shutdown', '-h', 'now'))
			sys.exit()
		else:
			CURRENT_ALARM = False

		# check for eclipsed threshold levels
		if charge > CTH:
			print "Learning High Threshold"
			#ProgramRegister(4, valHigh)
			#ProgramRegister(5, valLow)
		elif charge < CTL:
			print "Learning Low Threshold"
			#ProgramRegister(6, valHigh)
			#ProgramRegister(7, valLow)
		else:
			print "Value Within Limits"

		# save to a file
		with open(filename, "ab") as myfile:

			# save [time index][charge][hex value status][hex value control]
			s = '%d, %d, %d, %.3f, %.3f\n' %(dt, status, charge, voltage, current)
			if CURRENT_ALARM:
				s += CURRENT_ALARM + '\n'
			myfile.write(s)

		# restart ADC scan
		print "Restart ADC Read"
		ProgramRegister(0x01, (0x3C | 0x40))

		time.sleep(60)

	return


def MonitorBattery(verbose):

	# filename with datetime prepend
	filename = time.ctime() + '_BatteryLog.txt'
	with open(filename, "wb") as myfile:
			#create new file each run
			s = 'Minutes Index, Status Register, Accumulated Charge, Voltage, Current\n'
			myfile.write(s)
	while True:
		# time we execute the read - minute indexed
		dt = (int((time.time() - start) / 60))

		# call i2cget on the charge register (read as word)

		# get charge value
		valHigh = ReadRegisterByte(2)
		valLow = ReadRegisterByte(3)
		charge = (valHigh << 8) + valLow

		# grab current flow rate
		current_H = ReadRegisterByte(0x0E)
		current_L = ReadRegisterByte(0x0F)
		cur = float((current_H << 8) + current_L)
		current = (.05/.025) * ((cur - 32767)/32767)
		#print "\tCurrent %.2f" % current

		# grab voltage reading from last loop
		volt_H = ReadRegisterByte(8)
		volt_L = ReadRegisterByte(9)
		adc = float((volt_H << 8) + volt_L)
		voltage = (23.6 * (adc/65535))

		# call i2cget on the status register (read as byte)
		status = ReadRegisterByte(0)

		# Check status for any alarms. Not sure what to do with the alarms quite yet.
		if status & 0x40:
			# overflow - Not sure what to do with it?
			CURRENT_ALARM = "Overflow!!!"
		elif status & 0x08:
			# high limit
			CURRENT_ALARM = "high limit exceeded - Reset Threshold"
		elif status & 0x04:
			# low limit
			CURRENT_ALARM = "Low limit exceeded - stay here until we are actually dead?"
		elif status & 0x02:
			# low voltage alarm. Shut down now!

			CURRENT_ALARM =  "Low Voltage detected: %.2f" % voltage
			with open(filename, "ab") as myfile:
				s = '%d, %d, %d, %.3f, %.3f\n' %(dt, status, charge, voltage, current)
				if CURRENT_ALARM:
					s.append(CURRENT_ALARM + '\n')
				myfile.write(s)
			# shut down here.
			subprocess.call(('shutdown', '-h', 'now'))
			sys.exit()
		else:
			CURRENT_ALARM = False


		with open(filename, "ab") as myfile:

			# save [time index][charge][hex value status][hex value control]
			#s = dt + ',' + str(status) + ',' + str(charge) + ',' + ',' + str(voltage) + ',' + str(current) + '\n'
			s = '%d, %d, %d, %.3f, %.3f\n' %(dt, status, charge, voltage, current)
			if CURRENT_ALARM:
				s += CURRENT_ALARM + '\n'
			myfile.write(s)

		# print to the screen

		print time.ctime()
		print 'minutes index: %d' % dt
		print '\tCharge: ', charge
		print '\tStatus: ', status
		print '\tRAW ADC: %.3f' % adc
		print '\tVoltage: %.3fV' % voltage
		print '\tCurrent: %.3fA' % current
		if verbose:
			CTH_H = ReadRegisterByte(4)
			CTH_L = ReadRegisterByte(5)
			CTH = (CTH_H << 8) + CTH_L
			print "\tCTH is: %d" % (CTH)
			# get low threshold
			CTL_H = ReadRegisterByte(6)
			CTL_L = ReadRegisterByte(7)
			CTL = (CTL_H << 8) + CTL_L
			print "\tCTL is: %d" % CTL
			print "\tVolt_H is %d" % volt_H
			print "\tVolt_L is %d" % volt_L
			print "\tCurrent_H is %d" % current_H
			print "\tCurrent_L is %d" % current_L
			print "\tCharge_H is %d" % valHigh
			print "\tCharge_L is %d" % valLow

		# Turn on ADC to scan once. It will be read at the next monitor loop.
		# At the end of the monitor loop, restart scan
		print "Start ADC Read"
		ProgramRegister(0x01, (0x3C | 0x40))
		time.sleep(60)

	return

def Initialize(state):
	# Program low voltage threshold to 6v (1.0v per cell)
	# MSB: 0x41, LSB: 0x16
	# V(6.0) = 23.6 * (Vl/0xFFFF); Vl~16662
	# V(6.6) = 23.6 * (Vl/0xFFFF); Vl~18327 (0x4797)
	print "Program Low Voltage Level to 6.6V"
	ProgramRegister(0x0C, 0x47)
	ProgramRegister(0x0D, 0x97)

	# Turn on ADC to scan once. It will be read at the next monitor loop.
	# At the end of the monitor loop, restart scan
	print "Start ADC Read"
	ProgramRegister(0x01, (0x3C | 0x40))

	if (state):

		# shutdown Analog Measure
		print "presetting charge register to high value"
		ProgramRegister(1, (0x3C | 0x01))
		# Program Charge Registers
		ProgramRegister(2,0xF2)
		ProgramRegister(3,0xE4)
		# Turn on Analog Measure
		ProgramRegister(1, 0x3C)
		print "Setting Threshold limits"
		ProgramRegister(0x04, 0xF2)
		ProgramRegister(0x05, 0xE4)
		#print "Accumulated Charge Low: 3355"
		ProgramRegister(0x06, 0x0D)
		ProgramRegister(0x07, 0x1B)

	return

# time the script started (must be global)
start = int(time.time())
# grab any arguments from the console
# add argument to set log time, basically variable for time.sleep()
try:
	if (len(sys.argv) == 1):
		Initialize(0)
		MonitorBattery(0)
	else:
		if sys.argv[1] == "-h":
			print "Help menu\n\tUsage: \"python battery.py [-c | -h | -s | -v] [ -v (can only follow -s)]\""
			print " -h : this menu "
			print " -c : begin calibration cycle (being deprecated)"
			print " -s : Set the battery to fully charged"
			print " -v : Verbose. Print more to the console"
			print " default: monitor mode "
		elif sys.argv[1] == "-c":
			Initialize(0)
			CalibrateBattery()
		elif sys.argv[1] == "-s":
			Initialize(1)
			if (len(sys.argv) >= 2):
				if sys.argv[2] == "-v":
					MonitorBattery(1)
				else:
					print "Invalid arguments: %s" % sys.argv[2]
			else:
				MonitorBattery(0)
		elif sys.argv[1] == "-v":
			Initialize(0)
			MonitorBattery(1)
		else :
			print "\nInvalid arguments. \n\tUsage: battery.py [-c | -h | -s | -v] [ -v (can only follow -s)]"
			print " -h : Help menu "
			print " -c : Begin calibration cycle (being deprecated) "
			print " -s : Set the battery to be fully charged"
			print " -v : Verbose. Print more to the console"
			print " default: monitor mode "
except AttributeError as e:
	print "\nI hate typos.", e
except TypeError as e:
	print "\nThat was stupid.", e
except NameError as e:
	print "\nWTF? ", e
except KeyboardInterrupt:
	print "\nThe user has decided I should die. So sad."
	sys.exit()
except:
	print "\nThis is probably Brett's fault..., but yeah, I'm broken."
	print sys.exc_info()[0]
