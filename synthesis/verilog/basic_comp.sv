module mux(input sel, a, b, output y);
    assign y = sel ? b : a;
endmodule

module dff(input clk, rst, d, output reg q);
    always_ff @(posedge clk) begin
        if (rst) q <= 0;
        else     q <= d;
    end
endmodule

module ctr #(parameter W = 4) (
    input              clk, rst,
    output reg [W-1:0] count
);
    always_ff @(posedge clk) begin
        if (rst) count <= 0;
        else     count <= count + 1;
    end
endmodule

module fa(input a, b, cin, output sum, cout);
    assign sum  = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule

module sub(input a, b, bin, output diff, bout);
    assign diff = a ^ b ^ bin;
    assign bout = (~a & b) | (bin & ~(a ^ b));
endmodule

module inc(input a, cin, output sum, cout);
    assign sum  = a ^ cin;
    assign cout = a & cin;
endmodule

module cmp(input a, b, output lt);
    assign lt = (a < b);
endmodule

module bshift #(parameter WIDTH = 4) (
    input              clk, rst,
    input  [WIDTH-1:0] in,
    output reg [WIDTH-1:0] out
);
    always_ff @(posedge clk) begin
        if (rst) out <= 0;
        else     out <= in >> 1;
    end
endmodule
