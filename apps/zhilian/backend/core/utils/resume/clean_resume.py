def select_field_in_resume(rawResume_dict):
    clean_resume = {}
    dict_data = rawResume_dict

    dict_data_user = dict_data['user']

    clean_resume['user'] = {}

    clean_resume['user']['name'] = dict_data_user['name']
    clean_resume['user']['userActiveTag'] = dict_data_user['userActiveTag']
    clean_resume['user']['lastActiveTime'] = dict_data_user['lastActiveTime']
    clean_resume['user']['gender'] = dict_data_user['gender']
    clean_resume['user']['genderLabel'] = dict_data_user['genderLabel']
    clean_resume['user']['email'] = dict_data_user['email']
    clean_resume['user']['birthYear'] = dict_data_user['birthYear']
    clean_resume['user']['birthMonth'] = dict_data_user['birthMonth']
    clean_resume['user']['birthYearMonthLabel'] = dict_data_user['birthYearMonthLabel']
    clean_resume['user']['age'] = dict_data_user['age']
    clean_resume['user']['ageLabel'] = dict_data_user['ageLabel']
    clean_resume['user']['nationality'] = dict_data_user['nationality']
    clean_resume['user']['careerState'] = dict_data_user['careerState']
    clean_resume['user']['careerStateLabel'] = dict_data_user['careerStateLabel']
    clean_resume['user']['maxEducation'] = dict_data_user['maxEducation']
    clean_resume['user']['maxEducationLabel'] = dict_data_user['maxEducationLabel']
    clean_resume['user']['yearStartWorking'] = dict_data_user['yearStartWorking']
    clean_resume['user']['monthStartWorking'] = dict_data_user['monthStartWorking']
    clean_resume['user']['workYears'] = dict_data_user['workYears']
    clean_resume['user']['workMonths'] = dict_data_user['workMonths']
    clean_resume['user']['workYearsLabel'] = dict_data_user['workYearsLabel']
    clean_resume['user']['cityId'] = dict_data_user['cityId']
    clean_resume['user']['cityLabel'] = dict_data_user['cityLabel']
    clean_resume['user']['cityName'] = dict_data_user['cityName']
    clean_resume['user']['districtName'] = dict_data_user['districtName']
    clean_resume['user']['streetId'] = dict_data_user['streetId']
    clean_resume['user']['cityDistrictId'] = dict_data_user['cityDistrictId']
    clean_resume['user']['cityDistrictLabel'] = dict_data_user['cityDistrictLabel']

    clean_resume['candidate'] = dict_data['candidate']

    dict_data_resume = dict_data['resume']

    clean_resume['resume'] = {}
    clean_resume['resume']['language'] = dict_data_resume['language']
    clean_resume['resume']['name'] = dict_data_resume['name']
    clean_resume['resume']['resumeType'] = dict_data_resume['resumeType']
    clean_resume['resume']['resumeLevel'] = dict_data_resume['resumeLevel']
    clean_resume['resume']['educationExperienceTitle'] = dict_data_resume['educationExperienceTitle']
    clean_resume['resume']['educationExperiences'] = dict_data_resume['educationExperiences']

    clean_resume['resume']['workExperiences'] = []

    for index, workExperience in enumerate(dict_data_resume['workExperiences']):
        workExperience_dict = {}

        workExperience_dict['orgName'] = workExperience['orgName']
        workExperience_dict['orgNameHighlights'] = workExperience['orgNameHighlights']
        workExperience_dict['simpleOrgName'] = workExperience['simpleOrgName']
        workExperience_dict['industryType'] = workExperience['industryType']
        workExperience_dict['description'] = workExperience['description']
        workExperience_dict['descriptionHighlights'] = workExperience['descriptionHighlights']
        workExperience_dict['jobTitle'] = workExperience['jobTitle']
        workExperience_dict['jobTitleHighlights'] = workExperience['jobTitleHighlights']
        workExperience_dict['jobSubTitle'] = workExperience['jobSubTitle']
        workExperience_dict['jobSubtype'] = workExperience['jobSubtype']
        workExperience_dict['jobSubtypeHighlight'] = {}
        workExperience_dict['jobSubtypeHighlight']['name'] = workExperience['jobSubtypeHighlight']['name']
        workExperience_dict['salary'] = workExperience['salary']
        workExperience_dict['salaryDescription'] = workExperience['salaryDescription']
        workExperience_dict['salaryLabel'] = workExperience['salaryLabel']
        workExperience_dict['beginTime'] = workExperience['beginTime']
        workExperience_dict['endTime'] = workExperience['endTime']
        workExperience_dict['timeLabel'] = workExperience['timeLabel']

        clean_resume['resume']['workExperiences'].append(workExperience_dict)

    clean_resume['resume']['projectExperienceTitle'] = dict_data_resume['projectExperienceTitle']
    clean_resume['resume']['projectExperienceDescriptionTitle'] = dict_data_resume[
        'projectExperienceDescriptionTitle']
    clean_resume['resume']['projectExperiences'] = dict_data_resume['projectExperiences']
    clean_resume['resume']['languageSkillTitle'] = dict_data_resume['languageSkillTitle']
    clean_resume['resume']['languageSkillListeningTitle'] = dict_data_resume['languageSkillListeningTitle']
    clean_resume['resume']['languageSkillLiteracyTitle'] = dict_data_resume['languageSkillLiteracyTitle']
    clean_resume['resume']['languageSkills'] = dict_data_resume['languageSkills']

    return clean_resume
