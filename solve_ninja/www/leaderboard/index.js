frappe.ready(function() {
		get_users()
		$("#search").click(()=>{
			get_users(get_filters())
		})
		$("#clear").click(()=>{
			clear_filters()
			get_users()
		})
		$(".contribute-button").click(()=>{
			window.open("https://api.whatsapp.com/send/?phone=918095500118&text=testreg&type=phone_number&app_absent=0")
		})
});

var get_filters = function() {
		return {
			"ninja": $("#ninja").val(),
			"organization": $("#organization").val(),
			"city": $("#city").val(),
			"hr_range": $("#hr-range").val(),
		}
};

var clear_filters = function() {
	$("#ninja").val("")
	$("#organization").val("")
	$("#city").val("")
	$("#hr-range").val("")
}
var get_users = function(filters={}) {
		let rank_img = {
			1: "files/rank-1.png",
			2: "files/rank-2.png",
			3: "files/rank-3.png",
		}

		let org_based = 0
		const urlParams = new URLSearchParams(window.location.search);
		if (urlParams.get("org")) {
			filters["organization"] = urlParams.get("org")
		}

		frappe.call({
				method: "solve_ninja.api.common.search_users_",
				args: {
						"filters": filters
				},
				freeze: true,
				freeze_message: "...Searcing Users",
				callback: function(result) {
					let html = '';
						if (result.message.length > 0) {
							html = `<div class="container">
								<table class="table table-striped" style="text-align: center">
									<thead>
										<tr>
											<th>Rank</th>
											<th class="text-left">Name</th>
											<th class="text-left">City</th>
											<th class="text-right">Hours</th>
											<th class="text-right">Actions</th>
										</tr>
									</thead>
									<tbody>`
								result.message.forEach(leader => {
									let sr = leader.sr ? leader.sr : "";
									if (sr){
										if(rank_img[sr]) {
											sr = `<img src="${rank_img[sr]}" style="height: 42px" />`;
										}
									}
									let city = leader.city ? leader.city : "";

									html += `<tr>
									<td>
										<div>
											<span class="name-rank">${sr}</span>
										</div>
									</td>
									<td class="text-left" style="vertical-align: middle">
										<a href="/user-profile/${leader.username}" class="name-rank">${leader.full_name}</a>
									</td>
					
									<td class="text-left" style="vertical-align: middle">${city}</td>
									<td class="text-right" style="vertical-align: middle">${leader.hours_invested}</td>
									<td class="text-right" style="vertical-align: middle">${leader.contribution_count}</td>
								</tr>`
							});
							html += `</tbody>
								</table>
							</div>`
							$("#Ranktable").html(html)
						}
						
						else {
							html=`<div class="container">
								<div class="no-record">
									No Record Found
								</div>
							</div>`
							$("#Ranktable").html(html)
						}

						
						// if (!result || result.exc || !result.message || result.message.exc) {
								
						// } else {
						//     console.log(r.message)
						// }
				}
		});
}
