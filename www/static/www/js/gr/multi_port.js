(function ($) {
    //var new_tr = '<tr class="port-detail"><td class="details" colspan="7"><table><thead><tr><th>说明</th><th>变量名</th><th>变量值</th><th></th></tr></thead><tbody><tr><input type="hidden" name="d817c02e952344199e04e5c7ec6fa620_serviceNoChange" value="6521" /><td>连接地址</td><td>MYSQL_HOST</td><td>127.0.0.1</td><td></td></tr><tr><input type="hidden" name="d817c02e952344199e04e5c7ec6fa620_serviceNoChange" value="6522" /><td>端口</td><td>MYSQL_PORT</td><td>3309</td><td></td></tr><tr><td>用户名</td><td>MYSQL_USER</td><td>admin</td><td></td></tr><tr><td>密码</td><td>MYSQL_PASSWORD</td><td>d817c02e</td><td></td></tr></tbody></table></td><td class="details" colspan="5"><table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;"><tbody><tr><td>访问地址</td><td>op_mysql.goodrain.ali-sh-s1.goodrain.net</td></tr><tr><td>端口</td><td>12345</td></tr></tbody></table></td></tr>';
      //设定端口对内服务和对外服务的开关
      $('.switch-box').bootstrapSwitch();
      $('.switch-box').on('switchChange.bootstrapSwitch', function(event, state) {
        var port_switch = $(this);
          port = $(this).closest('tr').attr('port');
          port_type = $(this).attr('name'); //inner outer
          if (state) {
            action = "open_" + port_type;
          } else {
            action = 'close_' + port_type;
          }

          url = '/ajax/' + tenantName + '/' + serviceAlias + '/ports/' + port;
          $.post(url, {csrfmiddlewaretoken: $.cookie('csrftoken'), "action": action}, function(res){
            if(res.success){
                return;
            }else{
                port_switch.bootstrapSwitch('state', !state, true);
            }
          }, 'json');

        }
      );

      //显示端口明细
      $('.port-arrow a').click(function(event) {
        fold = $(this).attr('fold');
        if (fold == 'yes') {
          $(this).attr('fold', 'no');
          $(this).children('i').removeClass('fa-chevron-circle-right').addClass('fa-chevron-circle-down');
          curr_tr =  $(this).closest('tr');
          make_port_detail(curr_tr);
        } else {
          $(this).attr('fold', 'yes');
          $(this).children('i').removeClass('fa-chevron-circle-down').addClass('fa-chevron-circle-right');
          next_tr = $(this).closest('tr').next('tr');
          if (next_tr.hasClass('port-detail')) {
            next_tr.remove();
          }
        }
      });


      function make_port_detail (curr_tr) {
        
        url = '/ajax/' + tenantName + '/' + serviceAlias + '/ports/' + curr_tr.attr('port');
        $.get(url, function (event) {
          var next_tr = '<tr class="port-detail">';
          if (event.environment) {
            next_tr = next_tr + make_envs_html(event.environment);
          }
          if (event.outer_service) {
            next_tr = next_tr + make_outer_html(event.outer_service);
          }
          next_tr = next_tr + '</tr>'
          curr_tr.after(next_tr);
        });
      }

      function make_envs_html(data) {
        var prefix = '<td class="details" colspan="9"><table><thead><tr><th>说明</th><th>变量名</th><th>变量值</th><th></th></tr></thead><tbody>';
        var suffix = '</tbody></table></td>';
        var body = '';
        for (var order in data) {
          body = body + '<tr><td>' + data[order].desc + '</td><td>' + data[order].name + '</td><td>' + data[order].value + '</td></tr>';
        }
        return prefix + body + suffix;
      }

      function make_outer_html(data) {
        var prefix = '<td class="details" colspan="3"><table><tbody>';
        var suffix = '</tbody></table></td>';
        var body = '<tr><td>访问地址</td><td>' + data.domain + '</td><td>' + data.port + '</td></tr>';
        return prefix + body + suffix;
      }


      //即时修改端口别名和协议类型
      $(document).ready(function() {
        $('.edit-alias').editable({
          type: 'text',
          pk: 1,    
          title: '更改端口别名',
          ajaxOptions: {
              beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
                settings.data += '&action=rename_alias';
              },
          }
        });
        $('.edit-protocol').editable({
          type: 'select',
          source: [{value: "http", text: 'http'}, {value: "stream", text: 'stream'}],
          pk: 1,    
          ajaxOptions: {
              beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
                settings.data += '&action=change_protocol';
              },
          }
        });
      });

      //自定义环境变量
      $('#add_service_attr').click(function(event) {
        var msg = '<tr>'
        msg = msg + '<input type="hidden" name="attr_id" value="0">'
        msg = msg + '<td><input name ="name" type="text" value=""></td>'
        msg = msg + '<td><input name ="attr_name" type="text" value=""></td>'
        msg = msg + '<td><input name ="attr_value" type="text" value=""></td>' +
        '<td><div class="btn-toolbar" role="toolbar">' + 
          '<div class="btn-group" role="group">' + 
            '<button type="button" class="attr-save btn btn-success btn-xs" "><i class="fa fa-check"></i></button>' +
          '</div>' + 
          '<div class="btn-group" role="group">' + 
            '<button type="button" class="attr-cancel btn btn-danger btn-xs" "><i class="fa fa-times"></i></button></td>' +
          '</div>' + 
        '</div></td>'
        msg = msg + '</tr>'
        $("#envVartable tr:last").after(msg);
        $('.attr-cancel').unbind('click').bind('click', attr_cancel);
        $('.attr-save').unbind('click').bind('click', attr_save);
      });

      $('.attr-cancel').click(attr_cancel);

      $('.attr-delete').click(attr_delete);

      $('.attr-save').click(attr_save);

      function attr_cancel(event) {
        var cancel_tr = $(this).closest('tr');
        cancel_tr.remove();
      }

      function attr_delete(event) {
        var dict = {csrfmiddlewaretoken: $.cookie('csrftoken'), "action": "del_attr"};
        var del_tr = $(this).closest('tr');
        attr_name = del_tr.find('input["name"="' + attr_name + '"]').val();
        dict["attr_name"] = attr_name;

        url = '/ajax/' + tenantName + '/' + serviceAlias + '/custom-env';
        $.post(url, dict, function(res) {
          if (res.success) {
            del_tr.remove();
          }
        });
      }

      function attr_save(event) {
        var dict = {csrfmiddlewaretoken: $.cookie('csrftoken'), "action": "add_attr"};
        var add_tr = $(this).closest('tr');
        add_tr.find('input').each(function() {
          name = $(this).attr("name");
          value = $(this).val();
          dict[name] = value;
        });

        url = '/ajax/' + tenantName + '/' + serviceAlias + '/custom-env';
        $.post(url, dict, function(res) {
          if (res.success) {
            add_tr.find('.btn-toolbar').remove();
          }
        });
      }


})(jQuery);