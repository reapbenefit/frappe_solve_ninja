import frappe
from frappe.utils import cint
from solve_ninja.api.common import search_users_

sitemap = 1
no_cache = 1

def get_context(context):
	leaderboard_data_stats = search_users_()
	leaderboard_data = leaderboard_data_stats
	if len(leaderboard_data) > 10:
		leaderboard_data = leaderboard_data[:10]

	total_solve_ninjas = len(leaderboard_data)
	total_hours_invested = 0
	total_actions_taken = 0
	context.orgs = frappe.get_all("User Organization", pluck="name")
	context.cities = frappe.get_all("Samaaja Cities", pluck="name")
	# add count & default user image
	for count, data in enumerate(leaderboard_data):
		data["sr"] = count+1
		total_solve_ninjas = data["sr"]
		xs = (data['full_name'])
		name_list = xs.split()
		if(len(name_list) == 1):
			data['initials'] = name_list[0][0].upper()
		else:
			data['initials'] = name_list[0][0].upper() + name_list[1][0].upper()
		
		data["profile_link"] = "/user-profile/"+data.username
		
		
		user_badges = frappe.db.get_all('User badge', filters={'user':data['name']},fields=['badge'])
		curious_cat_badge = frappe.get_doc('Badge','Curious Cat')
		persona_counts=0
		persona = {
			'name':curious_cat_badge.title,
			'image':curious_cat_badge.icon,
			'description':str(curious_cat_badge.description).split("^")[0].strip(),
			'characteristics':str(curious_cat_badge.description).split("^")[1].strip().split("\n"),
		}
		for user_badge in user_badges:
			badge_doc = frappe.get_doc('Badge',user_badge.badge)
			badge_tags= badge_doc.get_tags()
	
			if badge_tags[0] == 'persona':
				if persona_counts == 0 :
					persona_counts = persona_counts+1
					persona['name']  = badge_doc.title
					persona['image'] = badge_doc.icon
					persona['description'] = str(badge_doc.description).split("^")[0].strip()
					persona['characteristics'] = str(badge_doc.description).split("^")[1].strip().split("\n")
				else:
					persona_counts = persona_counts+1

		if persona_counts > 1:
			action_ant_badge = frappe.get_doc('Badge','Action Ant')
			
			persona = {
				'name':action_ant_badge.title,
				'image':action_ant_badge.icon,
				'description':str(action_ant_badge.description).split("^")[0].strip(),
				'characteristics':str(action_ant_badge.description).split("^")[1].strip().split("\n"),
			}
		data["persona"] = persona

		
				
	for count, data in enumerate(leaderboard_data_stats):
		data["sr"] = count+1
		total_solve_ninjas = data["sr"]
		
		total_hours_invested = total_hours_invested + data['hours_invested']
		data['hours_invested'] = '%g'%(data['hours_invested'])
		total_actions_taken = total_actions_taken +data['contribution_count']
				
	context.leaderboard_data = leaderboard_data
	context.total_solve_ninjas = total_solve_ninjas
	context.total_hours_invested = int(total_hours_invested)
	context.total_actions_taken = total_actions_taken

	context.videos = [
		{
			"youtubeUrl": "https://www.youtube.com/embed/LVav-udl3ec",
			"title": "Reap Benefit Solve Ninja App: Explainer video",
			"description": "Understand what the Solve Ninja App does! Solve the public problems haunting your neighbourhood by either 1. Reporting to the officials 2. Campaigning and solving with the community 3. sharing products or ideas as Solutions"
		},
		{ 
			"youtubeUrl": "https://www.youtube.com/embed/wtu_OyoVzXM",
			"title": "About the Solve Ninja Movement",
			"description": "Co-Founder, Kuldeep Dantewadia talks about the work and impact of Reap Benefit" 
		},
		{
			"youtubeUrl": "https://www.youtube.com/embed/Dlox-PIC7xY",
			"title": "About the Solve Ninja Movement: CNN-IBN",
			"description": "Reap Benefit was featured on CNN-IBN last week on the 'Climate for Change' show. This is the video clipping of the show where Kuldeep Dantewadia and Gautam Prakash talk about the organisation's mission of solving local problems with young people through data driven, low cost innovations."
		},
		{ 
			"youtubeUrl": "https://www.youtube.com/embed/dSRD1Lbh0Sg",
			"title": "This Solve Ninja solved all the problems of his village by conducting that one 'meeting",
			"description": "The President of Ganjigatti Bala Cabinet Viresh, is the leader of all the children in his village." 
		},
		{
			"youtubeUrl": "https://www.youtube.com/embed/Hv19MzO6d7A",
			"title": "A young environmentalist plants more than 3000 plants a year! Solve Ninja Story from Reap Benefit",
			"description": "Here comes a story all the way from North!! Have you had a childhood where you enjoyed green neighbourhood clean air and pure drinking water ? What can you do to ensure that your children, the next generation also has a safe and healthy neighborhood? Here is a solve Ninja who is giving you answers to all your questions! Watch this story of a young environmentalist, Rajinder Singh from Barnala district, Punjab!! Youth of India are taking actions and  solving problems. Reap Benefit is here to support all the Problem solversð¤ comment ' Yuva cabinet' to know how to start your own Yuva cabinet in your area and become heros of your neighbourhood ð"
		}
	]
