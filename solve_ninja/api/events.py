import frappe
import json

@frappe.whitelist()
def get_action_html(action):
	action = frappe.db.get_value('Events', action, ['*'], as_dict=1)

	action_html = f"""<div class="action_item">
				<div class="action_item_head">
					<p>
						<svg viewBox="0 0 20 20">
							<path fill="#51A76A"
								d="M10.25,2.375c-4.212,0-7.625,3.413-7.625,7.625s3.413,7.625,7.625,7.625s7.625-3.413,7.625-7.625S14.462,2.375,10.25,2.375M10.651,16.811v-0.403c0-0.221-0.181-0.401-0.401-0.401s-0.401,0.181-0.401,0.401v0.403c-3.443-0.201-6.208-2.966-6.409-6.409h0.404c0.22,0,0.401-0.181,0.401-0.401S4.063,9.599,3.843,9.599H3.439C3.64,6.155,6.405,3.391,9.849,3.19v0.403c0,0.22,0.181,0.401,0.401,0.401s0.401-0.181,0.401-0.401V3.19c3.443,0.201,6.208,2.965,6.409,6.409h-0.404c-0.22,0-0.4,0.181-0.4,0.401s0.181,0.401,0.4,0.401h0.404C16.859,13.845,14.095,16.609,10.651,16.811 M12.662,12.412c-0.156,0.156-0.409,0.159-0.568,0l-2.127-2.129C9.986,10.302,9.849,10.192,9.849,10V5.184c0-0.221,0.181-0.401,0.401-0.401s0.401,0.181,0.401,0.401v4.651l2.011,2.008C12.818,12.001,12.818,12.256,12.662,12.412">
							</path>
						</svg>
						<span>{ frappe.utils.pretty_date(action.creation) }</span>
					</p>
				</div><h3>{action.title}</h3>"""

	if action.location_name:
		action_html = f"""{action_html}<p>
			<svg viewBox="0 0 20 20">
				<path fill="#51A76A"
					d="M10,1.375c-3.17,0-5.75,2.548-5.75,5.682c0,6.685,5.259,11.276,5.483,11.469c0.152,0.132,0.382,0.132,0.534,0c0.224-0.193,5.481-4.784,5.483-11.469C15.75,3.923,13.171,1.375,10,1.375 M10,17.653c-1.064-1.024-4.929-5.127-4.929-10.596c0-2.68,2.212-4.861,4.929-4.861s4.929,2.181,4.929,4.861C14.927,12.518,11.063,16.627,10,17.653 M10,3.839c-1.815,0-3.286,1.47-3.286,3.286s1.47,3.286,3.286,3.286s3.286-1.47,3.286-3.286S11.815,3.839,10,3.839 M10,9.589c-1.359,0-2.464-1.105-2.464-2.464S8.641,4.661,10,4.661s2.464,1.105,2.464,2.464S11.359,9.589,10,9.589">
				</path>
			</svg></p>"""
	
	if action.location_name:
		action_html = f"""{action_html}<p><span>{action.location_name}</span></p>"""
	
	if action.description:
		action_html = f"""{action_html}<p>{action.description}</p>"""

	action_html = f"""{action_html}</div>"""
	
	return action_html

@frappe.whitelist(allow_guest=True)
def submit_event_review(action):
	# frappe.errprint(action)
	action = json.loads(action)
	if not frappe.db.exists("Events Review", action.get("review")):
		frappe.throw("Invalid Review.")
	
	review = frappe.get_doc("Events Review", action.get("review"))
	review.update(action)
	review.flags.ignore_permissions = 1
	review.save()
	return action